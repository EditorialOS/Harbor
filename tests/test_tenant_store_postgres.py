"""Store contract checks against the ephemeral Postgres service used in CI."""

from __future__ import annotations

import os
import uuid

import pytest

from harbor.tenant_store import LATEST_SCHEMA_VERSION, TenantStore

pytestmark = pytest.mark.postgres


@pytest.fixture
def postgres_store() -> TenantStore:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return TenantStore(database_url)


def test_postgres_migrations_scoping_and_audit(postgres_store: TenantStore):
    suffix = uuid.uuid4().hex[:12]
    tenant_a = f"pg-a-{suffix}"
    tenant_b = f"pg-b-{suffix}"
    config = {"workers": ["newsletter-intelligence"], "connections": []}
    record_a, key_a = postgres_store.create_tenant(
        tenant_a, "Postgres A", "UTC", config
    )
    postgres_store.create_tenant(tenant_b, "Postgres B", "UTC", config)

    assert postgres_store.schema_version == LATEST_SCHEMA_VERSION
    assert postgres_store.resolve_api_key(key_a) == record_a
    assert postgres_store.claim_run(
        f"run-a-{suffix}", tenant_a, "newsletter-intelligence", "same-window"
    )
    assert not postgres_store.claim_run(
        f"run-a-duplicate-{suffix}", tenant_a, "newsletter-intelligence", "same-window"
    )
    assert postgres_store.claim_run(
        f"run-b-{suffix}", tenant_b, "newsletter-intelligence", "same-window"
    )
    recoverable_run = f"run-recoverable-{suffix}"
    assert postgres_store.claim_run(
        recoverable_run,
        tenant_a,
        "newsletter-intelligence",
        f"recoverable-{suffix}",
        lease_seconds=60,
    )
    with postgres_store._connect() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE runs SET lease_expires_at='2020-01-01T00:00:00+00:00' WHERE run_id=%s",
            (recoverable_run,),
        )
    assert postgres_store.reclaim_stale_run(recoverable_run, lease_seconds=60)
    assert not postgres_store.reclaim_stale_run(recoverable_run, lease_seconds=60)
    assert {run.run_id for run in postgres_store.list_runs(tenant_a)} >= {
        f"run-a-{suffix}",
        recoverable_run,
    }
    scheduled_run = f"run-scheduled-{suffix}"
    scheduled_window = f"schedule-v1:2026-09-06:0600:UTC:{suffix}"
    assert postgres_store.claim_run(
        scheduled_run,
        tenant_a,
        "newsletter-intelligence",
        scheduled_window,
    )
    postgres_store.begin_run_attempt(scheduled_run)
    postgres_store.finish_run(scheduled_run, "completed", {"status": "completed"})
    postgres_store.update_worker_schedule(
        tenant_a,
        "newsletter-intelligence",
        {"hour": 7, "minute": 30},
        "UTC",
        "2026-09-07T07:30:00+00:00",
    )
    state = postgres_store.get_schedule_state(tenant_a, "newsletter-intelligence")
    assert state is not None
    assert state.last_run_id == scheduled_run
    assert state.last_window_key == scheduled_window
    assert state.last_status == "completed"
    assert state.attempt_count == 1
    configured = postgres_store.configure_email_output(
        tenant_a,
        enabled=True,
        recipients=["owner@example.com"],
        subject_prefix="Morning brief",
    )
    assert "email" in configured.config["outputs"]
    delivery_id = f"delivery-{suffix}"
    assert postgres_store.claim_delivery(
        delivery_id,
        tenant_a,
        scheduled_run,
        "email",
        "recipient-fingerprint",
        f"delivery-key-{suffix}",
    )
    assert postgres_store.begin_delivery_attempt(delivery_id) == 1
    assert (
        postgres_store.finish_delivery(
            delivery_id, "delivered", provider_message_id="provider-123"
        ).status
        == "delivered"
    )
    assert "run.claimed" in {
        event.action for event in postgres_store.list_audit(tenant_a)
    }

    invited_tenant = f"pg-invite-{suffix}"
    _, invite_code = postgres_store.create_onboarding_invitation(
        f"owner-{suffix}@example.com"
    )
    _, invited_key = postgres_store.redeem_onboarding_invitation(
        invite_code,
        f"owner-{suffix}@example.com",
        invited_tenant,
        "Postgres Invited Workspace",
        "UTC",
        {"workers": ["newsletter-intelligence"], "connections": []},
    )
    session, session_token, csrf_token = postgres_store.create_web_session(
        invited_tenant
    )
    assert postgres_store.verify_api_key(invited_tenant, invited_key)
    assert postgres_store.resolve_web_session(session_token) == session
    assert postgres_store.verify_web_csrf(session, csrf_token)
    assert postgres_store.workspace_owner_email(invited_tenant) == (
        f"owner-{suffix}@example.com"
    )
    identity = postgres_store.bind_oauth_identity(
        "https://auth.example.com/",
        f"auth0|{suffix}",
        f"owner-{suffix}@example.com",
    )
    assert identity.tenant_id == invited_tenant
    assert (
        postgres_store.resolve_oauth_identity(
            "https://auth.example.com/", f"auth0|{suffix}"
        ).tenant_id
        == invited_tenant
    )
