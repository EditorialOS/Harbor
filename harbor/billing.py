"""Minimal Stripe Checkout billing adapter and verified entitlement events."""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from .tenant_store import BillingRecord, TenantStore, TenantStoreError


class BillingError(RuntimeError):
    pass


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    monthly_dollars: int
    source_limit: int
    api_access: bool
    price_environment: str


PLANS: tuple[Plan, ...] = (
    Plan("starter", "Starter", 29, 1, False, "STRIPE_PRICE_STARTER"),
    Plan("growth", "Growth", 79, 3, False, "STRIPE_PRICE_GROWTH"),
    Plan("scale", "Scale", 199, 100, True, "STRIPE_PRICE_SCALE"),
)
PLAN_BY_ID = {plan.id: plan for plan in PLANS}
ACTIVE_BILLING_STATUSES = {"active", "trialing"}


def billing_required() -> bool:
    return os.environ.get("HARBOR_BILLING_REQUIRED", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def billing_is_active(record: BillingRecord | None) -> bool:
    return bool(record and record.status in ACTIVE_BILLING_STATUSES)


class StripeBillingClient:
    def __init__(
        self,
        *,
        secret_key: str | None = None,
        webhook_secret: str | None = None,
        public_url: str | None = None,
    ):
        self.secret_key = secret_key or os.environ.get("STRIPE_SECRET_KEY", "")
        self.webhook_secret = webhook_secret or os.environ.get(
            "STRIPE_WEBHOOK_SECRET", ""
        )
        self.public_url = (
            public_url or os.environ.get("HARBOR_PUBLIC_URL", "")
        ).rstrip("/")

    def configured(self) -> bool:
        return bool(
            self.secret_key
            and self.webhook_secret
            and self.public_url
            and all(os.environ.get(plan.price_environment) for plan in PLANS)
        )

    def require_configuration(self) -> None:
        if not self.configured():
            raise BillingError("Stripe billing is not fully configured")
        parsed = urlsplit(self.public_url)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise BillingError("HARBOR_PUBLIC_URL must be an absolute HTTPS URL")

    def _price(self, plan: Plan) -> str:
        price = os.environ.get(plan.price_environment, "")
        if not price.startswith("price_"):
            raise BillingError(f"{plan.price_environment} is not configured")
        return price

    def plan_for_price(self, price_id: str) -> Plan | None:
        return next(
            (
                plan
                for plan in PLANS
                if os.environ.get(plan.price_environment) == price_id
            ),
            None,
        )

    def _post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        self.require_configuration()
        try:
            response = httpx.post(
                "https://api.stripe.com" + path,
                data=data,
                auth=(self.secret_key, ""),
                timeout=30,
            )
        except httpx.HTTPError as error:
            raise BillingError("Stripe is temporarily unavailable") from error
        if response.status_code < 200 or response.status_code >= 300:
            raise BillingError(
                f"Stripe request failed with HTTP {response.status_code}"
            )
        try:
            value = response.json()
        except ValueError as error:
            raise BillingError("Stripe returned an invalid response") from error
        if not isinstance(value, dict):
            raise BillingError("Stripe returned an invalid response")
        return value

    @staticmethod
    def _stripe_redirect(value: Any) -> str:
        if not isinstance(value, str):
            raise BillingError("Stripe did not return a checkout URL")
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not (
                parsed.hostname == "stripe.com"
                or parsed.hostname.endswith(".stripe.com")
            )
            or parsed.username
            or parsed.password
        ):
            raise BillingError("Stripe returned an invalid checkout URL")
        return value

    def create_checkout(
        self,
        tenant_id: str,
        email: str,
        plan_id: str,
        *,
        customer_id: str | None = None,
    ) -> str:
        plan = PLAN_BY_ID.get(plan_id)
        if plan is None:
            raise BillingError("Unknown Harbor plan")
        data: dict[str, Any] = {
            "mode": "subscription",
            "client_reference_id": tenant_id,
            "line_items[0][price]": self._price(plan),
            "line_items[0][quantity]": "1",
            "success_url": self.public_url + "/app?notice=billing_success",
            "cancel_url": self.public_url + "/app/billing?notice=billing_canceled",
            "metadata[tenant_id]": tenant_id,
            "metadata[plan]": plan.id,
            "subscription_data[metadata][tenant_id]": tenant_id,
            "subscription_data[metadata][plan]": plan.id,
            "allow_promotion_codes": "true",
        }
        if customer_id:
            data["customer"] = customer_id
        else:
            data["customer_email"] = email
        session = self._post("/v1/checkout/sessions", data)
        return self._stripe_redirect(session.get("url"))

    def create_portal(self, customer_id: str) -> str:
        if not customer_id.startswith("cus_"):
            raise BillingError("No Stripe customer is attached to this workspace")
        session = self._post(
            "/v1/billing_portal/sessions",
            {"customer": customer_id, "return_url": self.public_url + "/app"},
        )
        return self._stripe_redirect(session.get("url"))

    def verify_webhook(
        self,
        payload: bytes,
        signature_header: str,
        *,
        now: int | None = None,
        tolerance_seconds: int = 300,
    ) -> dict[str, Any]:
        if not self.webhook_secret:
            raise BillingError("Stripe webhook verification is not configured")
        parts: dict[str, list[str]] = {}
        for item in signature_header.split(","):
            key, separator, value = item.strip().partition("=")
            if separator:
                parts.setdefault(key, []).append(value)
        try:
            timestamp = int(parts["t"][0])
            signatures = parts["v1"]
        except (KeyError, IndexError, ValueError) as error:
            raise BillingError("Stripe webhook signature is invalid") from error
        current = int(time.time()) if now is None else now
        if abs(current - timestamp) > tolerance_seconds:
            raise BillingError("Stripe webhook timestamp is outside the allowed window")
        signed = str(timestamp).encode() + b"." + payload
        expected = hmac.new(
            self.webhook_secret.encode(), signed, hashlib.sha256
        ).hexdigest()
        if not any(
            hmac.compare_digest(expected, candidate) for candidate in signatures
        ):
            raise BillingError("Stripe webhook signature is invalid")
        try:
            event = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise BillingError("Stripe webhook payload is invalid") from error
        if (
            not isinstance(event, dict)
            or not isinstance(event.get("id"), str)
            or not isinstance(event.get("type"), str)
            or not isinstance((event.get("data") or {}).get("object"), dict)
        ):
            raise BillingError("Stripe webhook payload is invalid")
        return event


def _period_end(value: Any) -> str | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return dt.datetime.fromtimestamp(value, tz=dt.timezone.utc).isoformat()


def apply_stripe_event(
    store: TenantStore, client: StripeBillingClient, event: dict[str, Any]
) -> tuple[bool, str | None]:
    """Persist supported Stripe events and return (applied, activated tenant)."""
    event_type = event["type"]
    if event_type not in {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
        "checkout.session.async_payment_failed",
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        return False, None
    obj = event["data"]["object"]
    metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    customer_id = obj.get("customer") if isinstance(obj.get("customer"), str) else None
    tenant_id = metadata.get("tenant_id") or obj.get("client_reference_id")
    if not tenant_id and customer_id:
        tenant_id = store.billing_tenant_for_customer(customer_id)
    if not isinstance(tenant_id, str):
        raise BillingError("Stripe event is missing its Harbor workspace reference")

    plan_id = metadata.get("plan")
    price_id = None
    items = obj.get("items")
    if isinstance(items, dict):
        rows = items.get("data")
        if isinstance(rows, list) and rows:
            price = rows[0].get("price") if isinstance(rows[0], dict) else None
            if isinstance(price, dict):
                price_id = price.get("id")
    price_plan = client.plan_for_price(price_id) if isinstance(price_id, str) else None
    plan = price_plan or PLAN_BY_ID.get(plan_id)
    if plan is None:
        existing = store.get_billing(tenant_id)
        plan = PLAN_BY_ID.get(existing.plan) if existing else None
    if plan is None:
        raise BillingError("Stripe event does not match a Harbor plan")

    if event_type.startswith("checkout.session."):
        subscription_id = (
            obj.get("subscription")
            if isinstance(obj.get("subscription"), str)
            else None
        )
        payment_status = obj.get("payment_status")
        payment_succeeded = event_type == "checkout.session.async_payment_succeeded"
        payment_failed = event_type == "checkout.session.async_payment_failed"
        status = (
            "active"
            if payment_succeeded or payment_status in {"paid", "no_payment_required"}
            else "incomplete"
        )
        if payment_failed:
            status = "incomplete"
    else:
        subscription_id = obj.get("id") if isinstance(obj.get("id"), str) else None
        status = "canceled" if event_type.endswith(".deleted") else obj.get("status")
    if not isinstance(status, str):
        raise BillingError("Stripe event is missing subscription status")
    try:
        applied = store.apply_billing_event(
            event["id"],
            event_type,
            tenant_id,
            plan=plan.id,
            source_limit=plan.source_limit,
            api_access=plan.api_access,
            status=status,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            current_period_end=_period_end(obj.get("current_period_end")),
        )
    except TenantStoreError as error:
        raise BillingError("Stripe entitlement update failed") from error
    activated = tenant_id if status in ACTIVE_BILLING_STATUSES else None
    return applied, activated
