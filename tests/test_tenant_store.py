import datetime as dt
import hashlib
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
    assert store.resolve_api_key(key) == record
    assert store.resolve_api_key(key + "x") is None
    assert store.schema_version == LATEST_SCHEMA_VERSION

    store.set_active("acme", False)
    assert not store.verify_api_key("acme", key)
    assert store.resolve_api_key(key) is None


def test_run_idempotency(tmp_path: Path):
    store = TenantStore(f"sqlite:///{tmp_path / 'harbor.db'}")
    _create(store, "acme")
    _create(store, "beta")
    assert store.claim_run("run1", "acme", "newsletter-intelligence", "same-window")
    assert not store.claim_run("run2", "acme", "newsletter-intelligence", "same-window")
    assert store.claim_run("run3", "beta", "newsletter-intelligence", "same-window")
    assert store.claim_run("run4", "acme", "another-worker", "same-window")
    assert [run.run_id for run in store.list_runs("acme")] == ["run4", "run1"]
    assert [run.run_id for run in store.list_runs("beta")] == ["run3"]


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


def test_service_heartbeat_and_operational_snapshot_are_durable(tmp_path: Path):
    store = TenantStore(f"sqlite:///{tmp_path / 'operations.db'}")
    _create(store)
    heartbeat = store.upsert_service_heartbeat(
        "scheduler", "healthy", {"event_count": 2}
    )
    assert heartbeat.status == "healthy"
    assert heartbeat.metadata == {"event_count": 2}
    assert store.get_service_heartbeat("scheduler") == heartbeat

    store.upsert_schedule_state(
        "acme",
        "newsletter-intelligence",
        next_run_at="2020-01-01T00:00:00+00:00",
        last_status="scheduled",
    )
    assert store.claim_run(
        "stale-run",
        "acme",
        "newsletter-intelligence",
        "stale-window",
        lease_seconds=60,
    )
    snapshot = store.operational_snapshot(
        dt.datetime(2030, 1, 1, tzinfo=dt.timezone.utc)
    )

    assert snapshot["schema_version"] == LATEST_SCHEMA_VERSION
    assert snapshot["active_tenants"] == 1
    assert snapshot["runs"] == {"running": 1}
    assert snapshot["overdue_schedules"] == 1
    assert snapshot["expired_run_leases"] == 1
    assert snapshot["scheduler_heartbeat_status"] == "healthy"
    assert snapshot["scheduler_heartbeat_age_seconds"] is not None


def test_service_heartbeat_rejects_secret_metadata(tmp_path: Path):
    store = TenantStore(f"sqlite:///{tmp_path / 'heartbeat-secrets.db'}")
    with pytest.raises(TenantStoreError, match="plaintext secret-like field"):
        store.upsert_service_heartbeat(
            "scheduler", "failed", {"api_key": "must-not-be-stored"}
        )


def test_operational_snapshot_applies_schedule_overdue_grace(tmp_path: Path):
    store = TenantStore(f"sqlite:///{tmp_path / 'grace.db'}")
    _create(store)
    store.upsert_schedule_state(
        "acme",
        "newsletter-intelligence",
        next_run_at="2026-09-06T12:59:00+00:00",
        last_status="scheduled",
    )

    now = dt.datetime(2026, 9, 6, 13, 0, tzinfo=dt.timezone.utc)
    assert store.operational_snapshot(now)["overdue_schedules"] == 0
    assert (
        store.operational_snapshot(now, overdue_grace_seconds=0)["overdue_schedules"]
        == 1
    )


def test_invitation_redemption_and_web_sessions_store_only_hashes(tmp_path: Path):
    store = TenantStore(f"sqlite:///{tmp_path / 'onboarding.db'}")
    invitation, code = store.create_onboarding_invitation("Owner@Example.com")
    record, api_key = store.redeem_onboarding_invitation(
        code,
        "owner@example.com",
        "new-workspace",
        "New Workspace",
        "UTC",
        {
            "workers": ["newsletter-intelligence"],
            "schedule": {"newsletter-intelligence": {"hour": 6, "minute": 0}},
            "outputs": ["files"],
            "connections": [],
            "provisioning": {"status": "pending"},
        },
    )
    session, session_token, csrf_token = store.create_web_session(record.tenant_id)

    assert invitation.email == "owner@example.com"
    assert store.verify_api_key(record.tenant_id, api_key)
    assert store.workspace_owner_email(record.tenant_id) == "owner@example.com"
    assert store.resolve_web_session(session_token) == session
    assert store.verify_web_csrf(session, csrf_token)
    assert not store.verify_web_csrf(session, "wrong")
    with store._connect() as conn:
        invite_row = conn.execute(
            "SELECT code_hash,consumed_at,tenant_id FROM onboarding_invitations"
        ).fetchone()
        session_row = conn.execute(
            "SELECT token_hash,csrf_hash FROM web_sessions"
        ).fetchone()
        serialized = " ".join(str(value) for value in (*invite_row, *session_row))
    assert code not in serialized
    assert session_token not in serialized
    assert csrf_token not in serialized

    with pytest.raises(TenantStoreError, match="already been used"):
        store.redeem_onboarding_invitation(
            code,
            "owner@example.com",
            "another-workspace",
            "Another Workspace",
            "UTC",
            {"workers": [], "connections": []},
        )

    store.delete_web_session(session_token)
    assert store.resolve_web_session(session_token) is None


def test_invitation_rejects_wrong_email_and_expiry(tmp_path: Path):
    store = TenantStore(f"sqlite:///{tmp_path / 'invite-errors.db'}")
    _, code = store.create_onboarding_invitation("owner@example.com")
    with pytest.raises(TenantStoreError, match="does not match"):
        store.redeem_onboarding_invitation(
            code,
            "other@example.com",
            "wrong-email",
            "Wrong Email",
            "UTC",
            {"workers": [], "connections": []},
        )

    with store._connect() as conn:
        conn.execute(
            "UPDATE onboarding_invitations SET expires_at=? WHERE code_hash=?",
            ("2020-01-01T00:00:00+00:00", hashlib.sha256(code.encode()).hexdigest()),
        )
    with pytest.raises(TenantStoreError, match="expired"):
        store.redeem_onboarding_invitation(
            code,
            "owner@example.com",
            "expired-invite",
            "Expired Invite",
            "UTC",
            {"workers": [], "connections": []},
        )


def test_oauth_identity_binds_only_to_one_verified_workspace_owner(tmp_path: Path):
    store = TenantStore(f"sqlite:///{tmp_path / 'oauth.db'}")
    _create(store, "acme")
    store.set_workspace_owner("acme", "Owner@Example.com")

    bound = store.bind_oauth_identity(
        "https://auth.example.com/", "auth0|owner", "owner@example.com"
    )
    assert bound.tenant_id == "acme"
    assert (
        store.resolve_oauth_identity(
            "https://auth.example.com/", "auth0|owner"
        ).tenant_id
        == "acme"
    )
    assert "oauth.identity.bound" in {
        event.action for event in store.list_audit("acme")
    }

    with store._connect() as conn:
        row = conn.execute(
            "SELECT issuer,subject,tenant_id,email FROM oauth_identities"
        ).fetchone()
    assert tuple(row) == (
        "https://auth.example.com/",
        "auth0|owner",
        "acme",
        "owner@example.com",
    )


def test_oauth_identity_rejects_missing_or_ambiguous_owner(tmp_path: Path):
    store = TenantStore(f"sqlite:///{tmp_path / 'oauth-ambiguous.db'}")
    _create(store, "acme")
    _create(store, "beta")

    with pytest.raises(TenantStoreError, match="does not match"):
        store.bind_oauth_identity(
            "https://auth.example.com/", "auth0|missing", "missing@example.com"
        )

    store.set_workspace_owner("acme", "shared@example.com")
    store.set_workspace_owner("beta", "shared@example.com")
    with pytest.raises(TenantStoreError, match="more than one"):
        store.bind_oauth_identity(
            "https://auth.example.com/", "auth0|shared", "shared@example.com"
        )


def test_provisioning_failures_are_durable_and_sanitized(tmp_path: Path):
    store = TenantStore(f"sqlite:///{tmp_path / 'provisioning.db'}")
    _create(store)
    updated = store.record_provisioning_status(
        "acme", "failed", error_type="SpriteUnavailable", actor_type="web_onboarding"
    )
    assert updated.config["provisioning"]["status"] == "failed"
    assert updated.config["provisioning"]["error_type"] == "SpriteUnavailable"
    assert "tenant.provisioning.failed" in {
        event.action for event in store.list_audit("acme")
    }


def test_passwordless_login_code_is_tenant_scoped_single_use_and_hashed(
    tmp_path: Path,
):
    store = TenantStore(f"sqlite:///{tmp_path / 'passwordless.db'}")
    _create(store, "acme")
    store.set_workspace_owner("acme", "owner@example.com")

    code_id, code = store.create_web_login_code("OWNER@example.com")
    assert code_id.startswith("login_")
    assert len(code) == 10
    with store._connect() as conn:
        row = conn.execute(
            "SELECT code_hash,email,tenant_id,consumed_at FROM web_login_codes"
        ).fetchone()
    assert code not in row[0]
    assert row[1:3] == ("owner@example.com", "acme")
    assert row[3] is None

    assert store.redeem_web_login_code("owner@example.com", code).tenant_id == "acme"
    with pytest.raises(TenantStoreError, match="invalid or expired"):
        store.redeem_web_login_code("owner@example.com", code)
    with pytest.raises(TenantStoreError, match="does not match"):
        store.create_web_login_code("missing@example.com")


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
