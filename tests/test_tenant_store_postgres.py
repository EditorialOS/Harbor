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
    postgres_store.create_tenant(tenant_a, "Postgres A", "UTC", config)
    postgres_store.create_tenant(tenant_b, "Postgres B", "UTC", config)

    assert postgres_store.schema_version == LATEST_SCHEMA_VERSION
    assert postgres_store.claim_run(
        f"run-a-{suffix}", tenant_a, "newsletter-intelligence", "same-window"
    )
    assert not postgres_store.claim_run(
        f"run-a-duplicate-{suffix}", tenant_a, "newsletter-intelligence", "same-window"
    )
    assert postgres_store.claim_run(
        f"run-b-{suffix}", tenant_b, "newsletter-intelligence", "same-window"
    )
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
