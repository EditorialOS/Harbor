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
    assert "run.claimed" in {
        event.action for event in postgres_store.list_audit(tenant_a)
    }
