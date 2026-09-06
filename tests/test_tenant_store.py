import sqlite3
from pathlib import Path

import pytest

from harbor.tenant_store import (
    LATEST_SCHEMA_VERSION,
    TenantStore,
    TenantStoreError,
)


def _create(store: TenantStore, tenant_id: str = "acme") -> str:
    _, key = store.create_tenant(
        tenant_id,
        tenant_id.title(),
        "UTC",
        {"workers": ["newsletter-intelligence"], "connections": []},
    )
    return key


def test_tenant_store_issues_and_verifies_key(tmp_path: Path):
    store = TenantStore(f"sqlite:///{tmp_path / 'harbor.db'}")
    record, key = store.create_tenant(
        "acme",
        "Acme",
        "America/Los_Angeles",
        {"workers": ["newsletter-intelligence"], "connections": []},
    )
    assert record.tenant_id == "acme"
    assert key.startswith("harbor_")
    assert store.verify_api_key("acme", key)
    assert not store.verify_api_key("acme", key + "x")
    assert store.schema_version == LATEST_SCHEMA_VERSION

    store.set_active("acme", False)
    assert not store.verify_api_key("acme", key)


def test_run_idempotency(tmp_path: Path):
    store = TenantStore(f"sqlite:///{tmp_path / 'harbor.db'}")
    _create(store, "acme")
    _create(store, "beta")
    assert store.claim_run("run1", "acme", "newsletter-intelligence", "same-window")
    assert not store.claim_run("run2", "acme", "newsletter-intelligence", "same-window")
    assert store.claim_run("run3", "beta", "newsletter-intelligence", "same-window")
    assert store.claim_run("run4", "acme", "another-worker", "same-window")


def test_run_lease_can_only_be_reclaimed_after_expiry(tmp_path: Path):
    store = TenantStore(f"sqlite:///{tmp_path / 'harbor.db'}")
    _create(store)
    assert store.claim_run(
        "run1",
        "acme",
        "newsletter-intelligence",
        "same-window",
        lease_seconds=60,
    )
    record = store.get_run_by_idempotency(
        "acme", "newsletter-intelligence", "same-window"
    )
    assert record is not None
    assert record.lease_expires_at is not None
    assert not store.reclaim_stale_run("run1", lease_seconds=60)

    with store._connect() as conn:
        conn.execute(
            "UPDATE runs SET lease_expires_at=? WHERE run_id=?",
            ("2020-01-01T00:00:00+00:00", "run1"),
        )
    assert store.reclaim_stale_run("run1", lease_seconds=60)
    assert not store.reclaim_stale_run("run1", lease_seconds=60)
    assert "run.reclaimed" in {event.action for event in store.list_audit("acme")}


def test_claim_run_does_not_hide_database_errors(tmp_path: Path):
    store = TenantStore(f"sqlite:///{tmp_path / 'harbor.db'}")
    with pytest.raises(TenantStoreError, match="could not claim run"):
        store.claim_run("missing", "unknown", "newsletter-intelligence", "window")


def test_config_updates_and_audit_are_store_owned(tmp_path: Path):
    store = TenantStore(f"sqlite:///{tmp_path / 'harbor.db'}")
    _create(store)
    record = store.upsert_connection(
        "acme",
        {
            "id": "bee-main",
            "provider": "beehiiv",
            "settings": {
                "gateway_base_url": "https://api.sprites.dev/v1/gateway/custom_api/bee-main",
                "publication_id": "pub_example",
            },
        },
        actor_type="admin_api",
    )
    assert record.config["connections"][0]["id"] == "bee-main"

    record = store.record_connection_verification(
        "acme",
        "bee-main",
        {
            "status": "verified",
            "checked_at": "2026-09-06T00:00:00+00:00",
            "publication_id": "pub_example",
            "publication_name": "Example newsletter",
        },
    )
    assert record.config["connections"][0]["status"] == "verified"
    assert record.config["connections"][0]["last_error"] is None

    store.set_sprite("acme", "harbor-acme-example")
    assert store.get("acme").sprite_name == "harbor-acme-example"

    actions = {event.action for event in store.list_audit("acme")}
    assert {
        "tenant.created",
        "connection.upserted",
        "connection.verified",
        "tenant.sprite.assigned",
    } <= actions


def test_email_configuration_and_delivery_state_are_store_owned(tmp_path: Path):
    store = TenantStore(f"sqlite:///{tmp_path / 'harbor.db'}")
    _create(store)
    record = store.configure_email_output(
        "acme",
        enabled=True,
        recipients=["owner@example.com"],
        subject_prefix="Morning brief",
    )
    assert record.config["outputs"] == ["email"]
    assert record.config["output_settings"]["email"]["recipients"] == [
        "owner@example.com"
    ]

    assert store.claim_run(
        "run-email", "acme", "newsletter-intelligence", "email-window"
    )
    assert store.claim_delivery(
        "delivery-one",
        "acme",
        "run-email",
        "email",
        "recipient-fingerprint",
        "delivery-idempotency-key",
    )
    assert not store.claim_delivery(
        "delivery-two",
        "acme",
        "run-email",
        "email",
        "recipient-fingerprint",
        "delivery-idempotency-key",
    )
    assert store.begin_delivery_attempt("delivery-one") == 1
    delivered = store.finish_delivery(
        "delivery-one", "delivered", provider_message_id="provider-123"
    )
    assert delivered.status == "delivered"
    assert delivered.provider_message_id == "provider-123"
    assert delivered.delivered_at is not None
    assert {event.action for event in store.list_audit("acme")} >= {
        "output.email.configured",
        "delivery.claimed",
        "delivery.finished",
    }


def test_secret_shaped_connection_metadata_is_rejected(tmp_path: Path):
    store = TenantStore(f"sqlite:///{tmp_path / 'harbor.db'}")
    _create(store)
    with pytest.raises(TenantStoreError, match="plaintext secret-like field"):
        store.upsert_connection(
            "acme",
            {
                "id": "bad",
                "provider": "beehiiv",
                "settings": {"api_key": "must-not-be-stored"},
            },
        )
    assert store.get("acme").config["connections"] == []


def test_existing_alpha_sqlite_database_is_migrated(tmp_path: Path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE tenants (
                tenant_id TEXT PRIMARY KEY, name TEXT NOT NULL, timezone TEXT NOT NULL,
                sprite_name TEXT, api_key_hash TEXT NOT NULL, config_json TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE runs (
                run_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, worker_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE, status TEXT NOT NULL, result_json TEXT,
                started_at TEXT NOT NULL, finished_at TEXT
            );
            INSERT INTO tenants VALUES
                ('acme','Acme','UTC',NULL,'unused','{}',1,'2026-01-01','2026-01-01'),
                ('beta','Beta','UTC',NULL,'unused','{}',1,'2026-01-01','2026-01-01');
            INSERT INTO runs VALUES
                ('legacy-run','acme','newsletter-intelligence','window','completed','{}','2026-01-01',NULL);
            """
        )

    store = TenantStore(f"sqlite:///{path}")
    assert store.schema_version == LATEST_SCHEMA_VERSION
    with store._connect() as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
    assert "lease_expires_at" in columns
    assert store.claim_run("beta-run", "beta", "newsletter-intelligence", "window")
    assert not store.claim_run("acme-run", "acme", "newsletter-intelligence", "window")


def test_production_never_defaults_to_sqlite(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("HARBOR_ENV", "production")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(TenantStoreError, match="DATABASE_URL is required"):
        TenantStore()
