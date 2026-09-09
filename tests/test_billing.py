import hashlib
import hmac
import json
import time
from typing import ClassVar

import httpx
import pytest
from fastapi.testclient import TestClient

from harbor import control_plane
from harbor.billing import (
    BillingError,
    StripeBillingClient,
    apply_stripe_event,
    billing_is_active,
)
from harbor.scheduler import Scheduler
from harbor.tenant_store import TenantStore


def _stripe_env(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_not-real")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_not-real")
    monkeypatch.setenv("STRIPE_PRICE_STARTER", "price_starter")
    monkeypatch.setenv("STRIPE_PRICE_GROWTH", "price_growth")
    monkeypatch.setenv("STRIPE_PRICE_SCALE", "price_scale")
    monkeypatch.setenv("HARBOR_PUBLIC_URL", "https://harbor.example")


def _tenant(store, *, billing_required=True):
    record, key = store.create_tenant(
        "billing-tenant",
        "Billing Tenant",
        "UTC",
        {
            "workers": ["newsletter-intelligence"],
            "connections": [],
            "outputs": ["files"],
            "billing_required": billing_required,
        },
    )
    store.set_workspace_owner(record.tenant_id, "owner@example.com")
    return record, key


def _signature(payload: bytes, secret: str, timestamp: int) -> str:
    value = hmac.new(
        secret.encode(), str(timestamp).encode() + b"." + payload, hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={value}"


def test_checkout_and_portal_use_stripe_hosted_urls(monkeypatch):
    _stripe_env(monkeypatch)
    captured = []

    def fake_post(url, *, data, auth, timeout):
        captured.append((url, data, auth, timeout))
        if url.endswith("checkout/sessions"):
            return httpx.Response(
                200, json={"url": "https://checkout.stripe.com/c/pay/test"}
            )
        return httpx.Response(200, json={"url": "https://billing.stripe.com/p/session"})

    monkeypatch.setattr("httpx.post", fake_post)
    client = StripeBillingClient()
    checkout = client.create_checkout("billing-tenant", "owner@example.com", "starter")
    portal = client.create_portal("cus_example")

    assert checkout.startswith("https://checkout.stripe.com/")
    assert portal.startswith("https://billing.stripe.com/")
    assert captured[0][1]["mode"] == "subscription"
    assert captured[0][1]["line_items[0][price]"] == "price_starter"
    assert captured[0][1]["metadata[tenant_id]"] == "billing-tenant"
    assert captured[0][2] == ("sk_test_not-real", "")
    assert "sk_test_not-real" not in str(captured[0][1])


def test_verified_webhook_is_idempotent_and_updates_entitlement(tmp_path, monkeypatch):
    _stripe_env(monkeypatch)
    store = TenantStore(f"sqlite:///{tmp_path / 'billing.db'}")
    _tenant(store)
    event = {
        "id": "evt_checkout1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": "billing-tenant",
                "customer": "cus_example",
                "subscription": "sub_example",
                "metadata": {"tenant_id": "billing-tenant", "plan": "starter"},
            }
        },
    }
    payload = json.dumps(event, separators=(",", ":")).encode()
    client = StripeBillingClient()
    verified = client.verify_webhook(
        payload, _signature(payload, "whsec_not-real", 1000), now=1000
    )

    first, activated = apply_stripe_event(store, client, verified)
    second, _ = apply_stripe_event(store, client, verified)
    billing = store.get_billing("billing-tenant")

    assert first is True
    assert second is False
    assert activated == "billing-tenant"
    assert billing is not None and billing_is_active(billing)
    assert billing.plan == "starter"
    assert billing.source_limit == 1
    assert billing.stripe_customer_id == "cus_example"
    assert [e.action for e in store.list_audit("billing-tenant")].count(
        "billing.updated"
    ) == 1


def test_subscription_cancel_revokes_entitlement(tmp_path, monkeypatch):
    _stripe_env(monkeypatch)
    store = TenantStore(f"sqlite:///{tmp_path / 'billing-cancel.db'}")
    _tenant(store)
    client = StripeBillingClient()
    checkout = {
        "id": "evt_checkout2",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": "billing-tenant",
                "customer": "cus_example",
                "subscription": "sub_example",
                "metadata": {"plan": "growth"},
            }
        },
    }
    apply_stripe_event(store, client, checkout)
    canceled = {
        "id": "evt_cancel1",
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_example",
                "customer": "cus_example",
                "status": "canceled",
                "metadata": {"tenant_id": "billing-tenant", "plan": "growth"},
                "items": {"data": [{"price": {"id": "price_growth"}}]},
            }
        },
    }
    applied, activated = apply_stripe_event(store, client, canceled)

    assert applied is True
    assert activated is None
    assert store.get_billing("billing-tenant").status == "canceled"


def test_webhook_rejects_wrong_signature_and_old_timestamp(monkeypatch):
    _stripe_env(monkeypatch)
    client = StripeBillingClient()
    payload = b'{"id":"evt_bad","type":"ignored","data":{"object":{}}}'

    with pytest.raises(BillingError, match="signature"):
        client.verify_webhook(payload, "t=1000,v1=wrong", now=1000)
    with pytest.raises(BillingError, match="timestamp"):
        client.verify_webhook(
            payload, _signature(payload, "whsec_not-real", 1000), now=1400
        )


def test_unpaid_workspace_cannot_run_through_http_or_scheduler(tmp_path, monkeypatch):
    store = TenantStore(f"sqlite:///{tmp_path / 'billing-gate.db'}")
    record, key = store.create_tenant(
        "billing-tenant",
        "Billing Tenant",
        "UTC",
        {
            "workers": ["newsletter-intelligence"],
            "connections": [],
            "outputs": ["files"],
            "billing_required": True,
            "schedule": {"newsletter-intelligence": {"hour": 6, "minute": 0}},
        },
    )
    store.set_sprite(record.tenant_id, "harbor-billing-tenant")
    monkeypatch.setattr(control_plane, "store", store)
    client = TestClient(control_plane.app, base_url="https://testserver")

    response = client.post(
        "/v1/tenants/billing-tenant/workers/newsletter-intelligence/run",
        headers={"Authorization": f"Bearer {key}"},
        json={"input": {}, "idempotency_key": "unpaid-http"},
    )

    class NeverRunner:
        def run(self, sprite_name, run_spec):
            raise AssertionError("unpaid worker must not be dispatched")

    events = Scheduler(store, NeverRunner()).tick()
    assert response.status_code == 402
    assert events == []
    assert store.list_runs(record.tenant_id) == []


def test_paid_onboarding_provisions_only_after_verified_webhook(tmp_path, monkeypatch):
    _stripe_env(monkeypatch)
    monkeypatch.setenv("HARBOR_BILLING_REQUIRED", "true")
    store = TenantStore(f"sqlite:///{tmp_path / 'paid-onboarding.db'}")
    monkeypatch.setattr(control_plane, "store", store)

    class Runner:
        calls: ClassVar[list[str]] = []

        def provision(self, sprite_name):
            self.calls.append(sprite_name)
            return {"sprite_name": sprite_name, "status": "ready"}

    monkeypatch.setattr(control_plane, "SpriteRunner", Runner)
    client = TestClient(control_plane.app, base_url="https://testserver")
    _, invitation_code = store.create_onboarding_invitation("owner@example.com")

    created = client.post(
        "/onboarding",
        data={
            "invitation_code": invitation_code,
            "email": "owner@example.com",
            "workspace_name": "Paid Workspace",
            "timezone": "UTC",
            "hour": "6",
        },
        follow_redirects=False,
    )
    record = store.list_active()[0]
    assert created.status_code == 303
    assert created.headers["location"] == "/app/billing"
    assert record.sprite_name is None
    assert Runner.calls == []

    event = {
        "id": "evt_paid1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": record.tenant_id,
                "customer": "cus_paid",
                "subscription": "sub_paid",
                "metadata": {"tenant_id": record.tenant_id, "plan": "starter"},
            }
        },
    }
    payload = json.dumps(event, separators=(",", ":")).encode()
    delivered = client.post(
        "/stripe/webhook",
        content=payload,
        headers={
            "Stripe-Signature": _signature(payload, "whsec_not-real", int(time.time()))
        },
    )

    assert delivered.status_code == 200
    assert store.get(record.tenant_id).sprite_name == Runner.calls[0]
    assert billing_is_active(store.get_billing(record.tenant_id))
