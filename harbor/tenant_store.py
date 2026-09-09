"""Tenant, run, and audit state for Harbor's control plane.

SQLite is supported for local development. Production uses Postgres via
``DATABASE_URL``. Ordered, transactional migrations are recorded in
``schema_migrations``.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from dataclasses import dataclass
from typing import Any


class TenantStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class TenantRecord:
    tenant_id: str
    name: str
    timezone: str
    sprite_name: str | None
    config: dict[str, Any]
    active: bool = True


@dataclass(frozen=True)
class AuditRecord:
    audit_id: str
    tenant_id: str
    actor_type: str
    actor_id: str | None
    action: str
    target_type: str
    target_id: str | None
    metadata: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    tenant_id: str
    worker_id: str
    idempotency_key: str
    status: str
    result: dict[str, Any] | None
    started_at: str
    finished_at: str | None
    attempt_count: int
    last_error: str | None
    lease_expires_at: str | None


@dataclass(frozen=True)
class ScheduleState:
    tenant_id: str
    worker_id: str
    next_run_at: str
    last_window_key: str | None
    last_run_id: str | None
    last_status: str
    attempt_count: int
    last_error: str | None
    updated_at: str


@dataclass(frozen=True)
class DeliveryRecord:
    delivery_id: str
    tenant_id: str
    run_id: str
    adapter: str
    destination_fingerprint: str
    idempotency_key: str
    status: str
    provider_message_id: str | None
    attempt_count: int
    last_error: str | None
    created_at: str
    updated_at: str
    delivered_at: str | None


@dataclass(frozen=True)
class ServiceHeartbeat:
    service_id: str
    status: str
    metadata: dict[str, Any]
    updated_at: str


@dataclass(frozen=True)
class OnboardingInvitation:
    invitation_id: str
    email: str
    expires_at: str
    consumed_at: str | None
    tenant_id: str | None


@dataclass(frozen=True)
class WebSession:
    session_id: str
    tenant_id: str
    csrf_hash: str
    expires_at: str
    created_at: str


@dataclass(frozen=True)
class BillingRecord:
    tenant_id: str
    plan: str
    source_limit: int
    api_access: bool
    status: str
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    current_period_end: str | None
    updated_at: str


LATEST_SCHEMA_VERSION = 12

_SCHEMA_MIGRATIONS_SQLITE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
)
"""

_SQLITE_MIGRATIONS: tuple[tuple[int, str, tuple[str, ...]], ...] = (
    (
        1,
        "initial_tenants_and_runs",
        (
            """CREATE TABLE IF NOT EXISTS tenants (
                tenant_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                timezone TEXT NOT NULL,
                sprite_name TEXT,
                api_key_hash TEXT NOT NULL,
                config_json TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                result_json TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT
            )""",
        ),
    ),
    (
        2,
        "tenant_scoped_run_idempotency",
        (
            "DROP TABLE IF EXISTS runs_v2",
            """CREATE TABLE runs_v2 (
                run_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                worker_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                status TEXT NOT NULL,
                result_json TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                UNIQUE (tenant_id, worker_id, idempotency_key)
            )""",
            """INSERT INTO runs_v2
                (run_id, tenant_id, worker_id, idempotency_key, status,
                 result_json, started_at, finished_at)
                SELECT run_id, tenant_id, worker_id, idempotency_key, status,
                       result_json, started_at, finished_at FROM runs""",
            "DROP TABLE runs",
            "ALTER TABLE runs_v2 RENAME TO runs",
            "CREATE INDEX IF NOT EXISTS runs_tenant_started_idx ON runs (tenant_id, started_at DESC)",
        ),
    ),
    (
        3,
        "tenant_audit_log",
        (
            """CREATE TABLE IF NOT EXISTS audit_log (
                audit_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                actor_type TEXT NOT NULL,
                actor_id TEXT,
                action TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS audit_tenant_created_idx ON audit_log (tenant_id, created_at DESC)",
        ),
    ),
    (
        4,
        "scheduler_state_and_run_attempts",
        (
            "ALTER TABLE runs ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE runs ADD COLUMN last_error TEXT",
            """CREATE TABLE IF NOT EXISTS schedule_state (
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                worker_id TEXT NOT NULL,
                next_run_at TEXT NOT NULL,
                last_window_key TEXT,
                last_run_id TEXT,
                last_status TEXT NOT NULL,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, worker_id)
            )""",
        ),
    ),
    (
        5,
        "durable_output_deliveries",
        (
            """CREATE TABLE IF NOT EXISTS deliveries (
                delivery_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                adapter TEXT NOT NULL,
                destination_fingerprint TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                status TEXT NOT NULL,
                provider_message_id TEXT,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                delivered_at TEXT,
                UNIQUE (tenant_id, adapter, idempotency_key)
            )""",
            "CREATE INDEX IF NOT EXISTS deliveries_tenant_created_idx ON deliveries (tenant_id, created_at DESC)",
        ),
    ),
    (
        6,
        "recoverable_run_leases",
        (
            "ALTER TABLE runs ADD COLUMN lease_expires_at TEXT",
            "UPDATE runs SET lease_expires_at=started_at WHERE status='running'",
        ),
    ),
    (
        7,
        "indexed_tenant_api_key_hashes",
        (
            "CREATE INDEX IF NOT EXISTS tenants_api_key_hash_idx ON tenants (api_key_hash)",
        ),
    ),
    (
        8,
        "service_heartbeats",
        (
            """CREATE TABLE IF NOT EXISTS service_heartbeats (
                service_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""",
        ),
    ),
    (
        9,
        "web_onboarding_sessions",
        (
            """CREATE TABLE IF NOT EXISTS onboarding_invitations (
                invitation_id TEXT PRIMARY KEY,
                code_hash TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                consumed_at TEXT,
                tenant_id TEXT REFERENCES tenants(tenant_id),
                created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS workspace_owners (
                tenant_id TEXT PRIMARY KEY REFERENCES tenants(tenant_id),
                email TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS web_sessions (
                session_id TEXT PRIMARY KEY,
                token_hash TEXT NOT NULL UNIQUE,
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                csrf_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS web_sessions_tenant_idx ON web_sessions (tenant_id)",
        ),
    ),
    (
        10,
        "oauth_tenant_identities",
        (
            """CREATE TABLE IF NOT EXISTS oauth_identities (
                issuer TEXT NOT NULL,
                subject TEXT NOT NULL,
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                email TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                PRIMARY KEY (issuer, subject)
            )""",
            "CREATE INDEX IF NOT EXISTS oauth_identities_tenant_idx ON oauth_identities (tenant_id)",
        ),
    ),
    (
        11,
        "passwordless_web_login",
        (
            "CREATE INDEX IF NOT EXISTS workspace_owners_email_idx ON workspace_owners (LOWER(email))",
            """CREATE TABLE IF NOT EXISTS web_login_codes (
                code_id TEXT PRIMARY KEY,
                code_hash TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL,
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                expires_at TEXT NOT NULL,
                consumed_at TEXT,
                created_at TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS web_login_codes_email_idx ON web_login_codes (email, created_at DESC)",
        ),
    ),
    (
        12,
        "stripe_subscription_entitlements",
        (
            """CREATE TABLE IF NOT EXISTS billing_accounts (
                tenant_id TEXT PRIMARY KEY REFERENCES tenants(tenant_id),
                plan TEXT NOT NULL,
                source_limit INTEGER NOT NULL,
                api_access INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                stripe_customer_id TEXT UNIQUE,
                stripe_subscription_id TEXT UNIQUE,
                current_period_end TEXT,
                updated_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS billing_events (
                event_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                event_type TEXT NOT NULL,
                processed_at TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS billing_events_tenant_idx ON billing_events (tenant_id, processed_at DESC)",
        ),
    ),
)

_POSTGRES_MIGRATIONS: tuple[tuple[int, str, tuple[str, ...]], ...] = (
    (
        1,
        "initial_tenants_and_runs",
        (
            """CREATE TABLE IF NOT EXISTS tenants (
                tenant_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                timezone TEXT NOT NULL,
                sprite_name TEXT,
                api_key_hash TEXT NOT NULL,
                config_json JSONB NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                worker_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                result_json JSONB,
                started_at TIMESTAMPTZ NOT NULL,
                finished_at TIMESTAMPTZ
            )""",
        ),
    ),
    (
        2,
        "tenant_scoped_run_idempotency",
        (
            "ALTER TABLE runs DROP CONSTRAINT IF EXISTS runs_idempotency_key_key",
            """CREATE UNIQUE INDEX IF NOT EXISTS runs_tenant_worker_idempotency_uidx
                ON runs (tenant_id, worker_id, idempotency_key)""",
            "CREATE INDEX IF NOT EXISTS runs_tenant_started_idx ON runs (tenant_id, started_at DESC)",
        ),
    ),
    (
        3,
        "tenant_audit_log",
        (
            """CREATE TABLE IF NOT EXISTS audit_log (
                audit_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                actor_type TEXT NOT NULL,
                actor_id TEXT,
                action TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT,
                metadata_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS audit_tenant_created_idx ON audit_log (tenant_id, created_at DESC)",
        ),
    ),
    (
        4,
        "scheduler_state_and_run_attempts",
        (
            "ALTER TABLE runs ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE runs ADD COLUMN IF NOT EXISTS last_error TEXT",
            """CREATE TABLE IF NOT EXISTS schedule_state (
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                worker_id TEXT NOT NULL,
                next_run_at TIMESTAMPTZ NOT NULL,
                last_window_key TEXT,
                last_run_id TEXT,
                last_status TEXT NOT NULL,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                updated_at TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (tenant_id, worker_id)
            )""",
        ),
    ),
    (
        5,
        "durable_output_deliveries",
        (
            """CREATE TABLE IF NOT EXISTS deliveries (
                delivery_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                adapter TEXT NOT NULL,
                destination_fingerprint TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                status TEXT NOT NULL,
                provider_message_id TEXT,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                delivered_at TIMESTAMPTZ
            )""",
            """CREATE UNIQUE INDEX IF NOT EXISTS deliveries_tenant_adapter_idempotency_uidx
                ON deliveries (tenant_id, adapter, idempotency_key)""",
            "CREATE INDEX IF NOT EXISTS deliveries_tenant_created_idx ON deliveries (tenant_id, created_at DESC)",
        ),
    ),
    (
        6,
        "recoverable_run_leases",
        (
            "ALTER TABLE runs ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ",
            "UPDATE runs SET lease_expires_at=started_at WHERE status='running' AND lease_expires_at IS NULL",
        ),
    ),
    (
        7,
        "indexed_tenant_api_key_hashes",
        (
            "CREATE INDEX IF NOT EXISTS tenants_api_key_hash_idx ON tenants (api_key_hash)",
        ),
    ),
    (
        8,
        "service_heartbeats",
        (
            """CREATE TABLE IF NOT EXISTS service_heartbeats (
                service_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                metadata_json JSONB NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL
            )""",
        ),
    ),
    (
        9,
        "web_onboarding_sessions",
        (
            """CREATE TABLE IF NOT EXISTS onboarding_invitations (
                invitation_id TEXT PRIMARY KEY,
                code_hash TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                consumed_at TIMESTAMPTZ,
                tenant_id TEXT REFERENCES tenants(tenant_id),
                created_at TIMESTAMPTZ NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS workspace_owners (
                tenant_id TEXT PRIMARY KEY REFERENCES tenants(tenant_id),
                email TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS web_sessions (
                session_id TEXT PRIMARY KEY,
                token_hash TEXT NOT NULL UNIQUE,
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                csrf_hash TEXT NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS web_sessions_tenant_idx ON web_sessions (tenant_id)",
        ),
    ),
    (
        10,
        "oauth_tenant_identities",
        (
            """CREATE TABLE IF NOT EXISTS oauth_identities (
                issuer TEXT NOT NULL,
                subject TEXT NOT NULL,
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                email TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                last_seen_at TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (issuer, subject)
            )""",
            "CREATE INDEX IF NOT EXISTS oauth_identities_tenant_idx ON oauth_identities (tenant_id)",
        ),
    ),
    (
        11,
        "passwordless_web_login",
        (
            "CREATE INDEX IF NOT EXISTS workspace_owners_email_idx ON workspace_owners (LOWER(email))",
            """CREATE TABLE IF NOT EXISTS web_login_codes (
                code_id TEXT PRIMARY KEY,
                code_hash TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL,
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                expires_at TIMESTAMPTZ NOT NULL,
                consumed_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS web_login_codes_email_idx ON web_login_codes (email, created_at DESC)",
        ),
    ),
    (
        12,
        "stripe_subscription_entitlements",
        (
            """CREATE TABLE IF NOT EXISTS billing_accounts (
                tenant_id TEXT PRIMARY KEY REFERENCES tenants(tenant_id),
                plan TEXT NOT NULL,
                source_limit INTEGER NOT NULL,
                api_access BOOLEAN NOT NULL DEFAULT FALSE,
                status TEXT NOT NULL,
                stripe_customer_id TEXT UNIQUE,
                stripe_subscription_id TEXT UNIQUE,
                current_period_end TIMESTAMPTZ,
                updated_at TIMESTAMPTZ NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS billing_events (
                event_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                event_type TEXT NOT NULL,
                processed_at TIMESTAMPTZ NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS billing_events_tenant_idx ON billing_events (tenant_id, processed_at DESC)",
        ),
    ),
)

_FORBIDDEN_SECRET_KEYS = {
    "api_key",
    "access_token",
    "refresh_token",
    "authorization",
    "client_secret",
    "credential",
    "password",
    "secret",
    "token",
}


def _utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _lease_deadline(lease_seconds: int) -> str:
    if lease_seconds < 60 or lease_seconds > 86400:
        raise TenantStoreError("run lease must be between 60 and 86400 seconds")
    return (
        dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=lease_seconds)
    ).isoformat()


def _time_text(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def issue_tenant_key() -> str:
    return "harbor_" + secrets.token_urlsafe(32)


def _is_secret_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    if normalized == "secret_ref":
        return False
    return normalized in _FORBIDDEN_SECRET_KEYS or normalized.endswith(
        ("_api_key", "_access_token", "_refresh_token", "_password", "_secret")
    )


def validate_non_secret_metadata(value: Any, path: str = "metadata") -> None:
    """Reject plaintext credential-shaped fields before metadata is persisted."""
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if _is_secret_key(str(key)) and child not in (None, "", "REDACTED"):
                raise TenantStoreError(
                    f"plaintext secret-like field '{child_path}' is not allowed in Harbor state"
                )
            validate_non_secret_metadata(child, child_path)
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            validate_non_secret_metadata(child, f"{path}[{index}]")


class TenantStore:
    def __init__(self, database_url: str | None = None):
        configured_url = database_url or os.environ.get("DATABASE_URL")
        production = os.environ.get("HARBOR_ENV", "").lower() == "production" or bool(
            os.environ.get("FLY_APP_NAME")
        )
        if not configured_url and production:
            raise TenantStoreError(
                "DATABASE_URL is required in production; SQLite is local-development only"
            )
        self.database_url = configured_url or "sqlite:///harbor.db"
        if self.database_url.startswith(("postgres://", "postgresql://")):
            self.kind = "postgres"
        elif self.database_url.startswith("sqlite:///"):
            self.kind = "sqlite"
        else:
            raise TenantStoreError(
                "unsupported DATABASE_URL; use sqlite:///... or postgresql://..."
            )
        self._migrate()

    def _sqlite_path(self) -> str:
        return self.database_url.removeprefix("sqlite:///")

    def _connect(self):
        if self.kind == "sqlite":
            conn = sqlite3.connect(self._sqlite_path())
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        try:
            import psycopg  # type: ignore
        except ImportError as e:
            raise TenantStoreError(
                "Install psycopg[binary] for Postgres production"
            ) from e
        return psycopg.connect(self.database_url)

    def _migrate(self) -> None:
        try:
            if self.kind == "sqlite":
                self._migrate_sqlite()
            else:
                self._migrate_postgres()
        except TenantStoreError:
            raise
        except Exception as e:
            raise TenantStoreError(f"database migration failed: {e}") from e

    def _migrate_sqlite(self) -> None:
        with self._connect() as conn:
            conn.execute(_SCHEMA_MIGRATIONS_SQLITE)
            conn.execute("BEGIN IMMEDIATE")
            applied = {
                row[0] for row in conn.execute("SELECT version FROM schema_migrations")
            }
            for version, name, statements in _SQLITE_MIGRATIONS:
                if version in applied:
                    continue
                for statement in statements:
                    conn.execute(statement)
                conn.execute(
                    "INSERT INTO schema_migrations (version,name,applied_at) VALUES (?,?,?)",
                    (version, name, _utcnow()),
                )

    def _migrate_postgres(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtext('harbor_schema_migrations'))"
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                        version INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        applied_at TIMESTAMPTZ NOT NULL
                    )"""
            )
            cur.execute("SELECT version FROM schema_migrations")
            applied = {row[0] for row in cur.fetchall()}
            for version, name, statements in _POSTGRES_MIGRATIONS:
                if version in applied:
                    continue
                for statement in statements:
                    cur.execute(statement)
                cur.execute(
                    "INSERT INTO schema_migrations (version,name,applied_at) VALUES (%s,%s,%s)",
                    (version, name, _utcnow()),
                )

    @property
    def schema_version(self) -> int:
        with self._connect() as conn:
            if self.kind == "sqlite":
                row = conn.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
                ).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
                    )
                    row = cur.fetchone()
        return int(row[0])

    def _insert_audit(
        self,
        conn: Any,
        tenant_id: str,
        action: str,
        target_type: str,
        target_id: str | None = None,
        *,
        actor_type: str = "system",
        actor_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        metadata = metadata or {}
        validate_non_secret_metadata(metadata, "audit.metadata")
        values = (
            "audit_" + secrets.token_hex(16),
            tenant_id,
            actor_type,
            actor_id,
            action,
            target_type,
            target_id,
            json.dumps(metadata),
            _utcnow(),
        )
        if self.kind == "sqlite":
            conn.execute(
                """INSERT INTO audit_log
                   (audit_id,tenant_id,actor_type,actor_id,action,target_type,target_id,metadata_json,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                values,
            )
        else:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO audit_log
                       (audit_id,tenant_id,actor_type,actor_id,action,target_type,target_id,metadata_json,created_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                    values,
                )

    def create_tenant(
        self,
        tenant_id: str,
        name: str,
        timezone: str,
        config: dict[str, Any],
    ) -> tuple[TenantRecord, str]:
        validate_non_secret_metadata(config, "tenant.config")
        api_key = issue_tenant_key()
        now = _utcnow()
        payload = json.dumps(config)
        try:
            with self._connect() as conn:
                values = (
                    tenant_id,
                    name,
                    timezone,
                    None,
                    _hash_key(api_key),
                    payload,
                    True,
                    now,
                    now,
                )
                if self.kind == "sqlite":
                    conn.execute(
                        """INSERT INTO tenants
                           (tenant_id,name,timezone,sprite_name,api_key_hash,config_json,active,created_at,updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        values,
                    )
                else:
                    with conn.cursor() as cur:
                        cur.execute(
                            """INSERT INTO tenants
                               (tenant_id,name,timezone,sprite_name,api_key_hash,config_json,active,created_at,updated_at)
                               VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)""",
                            values,
                        )
                self._insert_audit(
                    conn, tenant_id, "tenant.created", "tenant", tenant_id
                )
        except Exception as e:
            raise TenantStoreError(f"could not create tenant '{tenant_id}': {e}") from e
        return self.get(tenant_id), api_key

    def create_onboarding_invitation(
        self,
        email: str,
        *,
        expires_in_hours: int = 24,
    ) -> tuple[OnboardingInvitation, str]:
        normalized_email = email.strip().lower()
        if len(normalized_email) > 254 or not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email
        ):
            raise TenantStoreError("invitation email is invalid")
        if expires_in_hours < 1 or expires_in_hours > 168:
            raise TenantStoreError(
                "invitation lifetime must be between 1 and 168 hours"
            )
        invitation_id = "invite_" + secrets.token_hex(16)
        code = "harbor-invite-" + secrets.token_urlsafe(32)
        now = dt.datetime.now(dt.timezone.utc)
        expires_at = now + dt.timedelta(hours=expires_in_hours)
        values = (
            invitation_id,
            _hash_key(code),
            normalized_email,
            expires_at.isoformat(),
            now.isoformat(),
        )
        with self._connect() as conn:
            if self.kind == "sqlite":
                conn.execute(
                    """INSERT INTO onboarding_invitations
                       (invitation_id,code_hash,email,expires_at,created_at)
                       VALUES (?,?,?,?,?)""",
                    values,
                )
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO onboarding_invitations
                           (invitation_id,code_hash,email,expires_at,created_at)
                           VALUES (%s,%s,%s,%s,%s)""",
                        values,
                    )
        return (
            OnboardingInvitation(
                invitation_id=invitation_id,
                email=normalized_email,
                expires_at=expires_at.isoformat(),
                consumed_at=None,
                tenant_id=None,
            ),
            code,
        )

    def redeem_onboarding_invitation(
        self,
        code: str,
        email: str,
        tenant_id: str,
        name: str,
        timezone: str,
        config: dict[str, Any],
    ) -> tuple[TenantRecord, str]:
        """Atomically consume an invitation and create its tenant workspace."""
        validate_non_secret_metadata(config, "tenant.config")
        normalized_email = email.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,63}", tenant_id):
            raise TenantStoreError("generated tenant id is invalid")
        if not name.strip() or len(name.strip()) > 200:
            raise TenantStoreError("workspace name is invalid")
        api_key = issue_tenant_key()
        now = dt.datetime.now(dt.timezone.utc)
        now_text = now.isoformat()
        payload = json.dumps(config)
        code_hash = _hash_key(code)
        placeholder = "?" if self.kind == "sqlite" else "%s"
        select_sql = (
            "SELECT invitation_id,email,expires_at,consumed_at "
            f"FROM onboarding_invitations WHERE code_hash={placeholder}"
        )
        if self.kind == "postgres":
            select_sql += " FOR UPDATE"
        try:
            with self._connect() as conn:
                if self.kind == "sqlite":
                    conn.execute("BEGIN IMMEDIATE")
                    invitation = conn.execute(select_sql, (code_hash,)).fetchone()
                else:
                    with conn.cursor() as cur:
                        cur.execute(select_sql, (code_hash,))
                        invitation = cur.fetchone()
                if not invitation:
                    raise TenantStoreError("invitation code is invalid")
                if invitation[3] is not None:
                    raise TenantStoreError("invitation code has already been used")
                expires_at = dt.datetime.fromisoformat(_time_text(invitation[2]) or "")
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=dt.timezone.utc)
                if expires_at <= now:
                    raise TenantStoreError("invitation code has expired")
                if not hmac.compare_digest(str(invitation[1]), normalized_email):
                    raise TenantStoreError("email does not match this invitation")

                tenant_values = (
                    tenant_id,
                    name.strip(),
                    timezone,
                    None,
                    _hash_key(api_key),
                    payload,
                    True,
                    now_text,
                    now_text,
                )
                if self.kind == "sqlite":
                    conn.execute(
                        """INSERT INTO tenants
                           (tenant_id,name,timezone,sprite_name,api_key_hash,config_json,
                            active,created_at,updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        tenant_values,
                    )
                    conn.execute(
                        "INSERT INTO workspace_owners (tenant_id,email,created_at) VALUES (?,?,?)",
                        (tenant_id, normalized_email, now_text),
                    )
                    updated = conn.execute(
                        """UPDATE onboarding_invitations
                           SET consumed_at=?,tenant_id=?
                           WHERE invitation_id=? AND consumed_at IS NULL""",
                        (now_text, tenant_id, invitation[0]),
                    ).rowcount
                else:
                    with conn.cursor() as cur:
                        cur.execute(
                            """INSERT INTO tenants
                               (tenant_id,name,timezone,sprite_name,api_key_hash,config_json,
                                active,created_at,updated_at)
                               VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)""",
                            tenant_values,
                        )
                        cur.execute(
                            """INSERT INTO workspace_owners
                               (tenant_id,email,created_at) VALUES (%s,%s,%s)""",
                            (tenant_id, normalized_email, now_text),
                        )
                        cur.execute(
                            """UPDATE onboarding_invitations
                               SET consumed_at=%s,tenant_id=%s
                               WHERE invitation_id=%s AND consumed_at IS NULL""",
                            (now_text, tenant_id, invitation[0]),
                        )
                        updated = cur.rowcount
                if updated != 1:
                    raise TenantStoreError("invitation code could not be consumed")
                self._insert_audit(
                    conn,
                    tenant_id,
                    "tenant.created",
                    "tenant",
                    tenant_id,
                    actor_type="web_onboarding",
                    metadata={"owner_email": normalized_email},
                )
        except TenantStoreError:
            raise
        except Exception as error:
            raise TenantStoreError("workspace could not be created") from error
        return self.get(tenant_id), api_key

    def create_web_session(
        self,
        tenant_id: str,
        *,
        expires_in_hours: int = 24 * 30,
    ) -> tuple[WebSession, str, str]:
        if expires_in_hours < 1 or expires_in_hours > 24 * 90:
            raise TenantStoreError("web session lifetime is invalid")
        tenant = self.get(tenant_id)
        if not tenant.active:
            raise TenantStoreError("tenant is inactive")
        session_id = "session_" + secrets.token_hex(16)
        token = "harbor-session-" + secrets.token_urlsafe(32)
        csrf_token = "harbor-csrf-" + secrets.token_urlsafe(32)
        now = dt.datetime.now(dt.timezone.utc)
        expires_at = now + dt.timedelta(hours=expires_in_hours)
        values = (
            session_id,
            _hash_key(token),
            tenant_id,
            _hash_key(csrf_token),
            expires_at.isoformat(),
            now.isoformat(),
        )
        with self._connect() as conn:
            if self.kind == "sqlite":
                conn.execute(
                    """INSERT INTO web_sessions
                       (session_id,token_hash,tenant_id,csrf_hash,expires_at,created_at)
                       VALUES (?,?,?,?,?,?)""",
                    values,
                )
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO web_sessions
                           (session_id,token_hash,tenant_id,csrf_hash,expires_at,created_at)
                           VALUES (%s,%s,%s,%s,%s,%s)""",
                        values,
                    )
        return (
            WebSession(
                session_id=session_id,
                tenant_id=tenant_id,
                csrf_hash=_hash_key(csrf_token),
                expires_at=expires_at.isoformat(),
                created_at=now.isoformat(),
            ),
            token,
            csrf_token,
        )

    def resolve_web_session(self, token: str) -> WebSession | None:
        if not token:
            return None
        placeholder = "?" if self.kind == "sqlite" else "%s"
        active_predicate = "t.active=1" if self.kind == "sqlite" else "t.active=TRUE"
        sql = (
            "SELECT s.session_id,s.tenant_id,s.csrf_hash,s.expires_at,s.created_at "
            "FROM web_sessions s JOIN tenants t ON t.tenant_id=s.tenant_id "
            f"WHERE s.token_hash={placeholder} AND {active_predicate}"
        )
        with self._connect() as conn:
            if self.kind == "sqlite":
                row = conn.execute(sql, (_hash_key(token),)).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, (_hash_key(token),))
                    row = cur.fetchone()
        if not row:
            return None
        expires_at = dt.datetime.fromisoformat(_time_text(row[3]) or "")
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=dt.timezone.utc)
        if expires_at <= dt.datetime.now(dt.timezone.utc):
            return None
        return WebSession(
            session_id=row[0],
            tenant_id=row[1],
            csrf_hash=row[2],
            expires_at=expires_at.astimezone(dt.timezone.utc).isoformat(),
            created_at=_time_text(row[4]) or "",
        )

    def verify_web_csrf(self, session: WebSession, csrf_token: str) -> bool:
        return bool(csrf_token) and hmac.compare_digest(
            session.csrf_hash, _hash_key(csrf_token)
        )

    def delete_web_session(self, token: str) -> None:
        placeholder = "?" if self.kind == "sqlite" else "%s"
        with self._connect() as conn:
            if self.kind == "sqlite":
                conn.execute(
                    f"DELETE FROM web_sessions WHERE token_hash={placeholder}",
                    (_hash_key(token),),
                )
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        f"DELETE FROM web_sessions WHERE token_hash={placeholder}",
                        (_hash_key(token),),
                    )

    def workspace_owner_email(self, tenant_id: str) -> str | None:
        placeholder = "?" if self.kind == "sqlite" else "%s"
        sql = f"SELECT email FROM workspace_owners WHERE tenant_id={placeholder}"
        with self._connect() as conn:
            if self.kind == "sqlite":
                row = conn.execute(sql, (tenant_id,)).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, (tenant_id,))
                    row = cur.fetchone()
        return str(row[0]) if row else None

    def owner_tenant_for_email(self, email: str) -> TenantRecord | None:
        normalized_email = email.strip().lower()
        placeholder = "?" if self.kind == "sqlite" else "%s"
        active_predicate = "t.active=1" if self.kind == "sqlite" else "t.active=TRUE"
        sql = (
            "SELECT o.tenant_id FROM workspace_owners o "
            "JOIN tenants t ON t.tenant_id=o.tenant_id "
            f"WHERE LOWER(o.email)={placeholder} AND {active_predicate}"
        )
        with self._connect() as conn:
            if self.kind == "sqlite":
                rows = conn.execute(sql, (normalized_email,)).fetchall()
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, (normalized_email,))
                    rows = cur.fetchall()
        tenant_ids = sorted({str(row[0]) for row in rows})
        if not tenant_ids:
            return None
        if len(tenant_ids) != 1:
            raise TenantStoreError("email matches more than one Harbor workspace")
        return self.get(tenant_ids[0])

    def create_web_login_code(
        self, email: str, *, expires_in_minutes: int = 15
    ) -> tuple[str, str]:
        """Issue a short-lived email code while persisting only its hash."""
        normalized_email = email.strip().lower()
        tenant = self.owner_tenant_for_email(normalized_email)
        if tenant is None:
            raise TenantStoreError("email does not match a Harbor workspace")
        if expires_in_minutes < 5 or expires_in_minutes > 60:
            raise TenantStoreError("login code lifetime is invalid")
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        code = "".join(secrets.choice(alphabet) for _ in range(10))
        code_id = "login_" + secrets.token_hex(16)
        now = dt.datetime.now(dt.timezone.utc)
        expires_at = now + dt.timedelta(minutes=expires_in_minutes)
        values = (
            code_id,
            _hash_key(code),
            normalized_email,
            tenant.tenant_id,
            expires_at.isoformat(),
            now.isoformat(),
        )
        with self._connect() as conn:
            if self.kind == "sqlite":
                conn.execute(
                    "UPDATE web_login_codes SET consumed_at=? WHERE tenant_id=? AND consumed_at IS NULL",
                    (now.isoformat(), tenant.tenant_id),
                )
                conn.execute(
                    """INSERT INTO web_login_codes
                       (code_id,code_hash,email,tenant_id,expires_at,created_at)
                       VALUES (?,?,?,?,?,?)""",
                    values,
                )
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE web_login_codes SET consumed_at=%s WHERE tenant_id=%s AND consumed_at IS NULL",
                        (now.isoformat(), tenant.tenant_id),
                    )
                    cur.execute(
                        """INSERT INTO web_login_codes
                           (code_id,code_hash,email,tenant_id,expires_at,created_at)
                           VALUES (%s,%s,%s,%s,%s,%s)""",
                        values,
                    )
            self._insert_audit(
                conn,
                tenant.tenant_id,
                "web.login_code.issued",
                "web_login_code",
                code_id,
                actor_type="web_auth",
            )
        return code_id, code

    def redeem_web_login_code(self, email: str, code: str) -> TenantRecord:
        normalized_email = email.strip().lower()
        normalized_code = code.strip().upper()
        placeholder = "?" if self.kind == "sqlite" else "%s"
        sql = (
            "SELECT code_id,tenant_id,expires_at,consumed_at FROM web_login_codes "
            f"WHERE email={placeholder} AND code_hash={placeholder}"
        )
        if self.kind == "postgres":
            sql += " FOR UPDATE"
        now = dt.datetime.now(dt.timezone.utc)
        with self._connect() as conn:
            if self.kind == "sqlite":
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    sql, (normalized_email, _hash_key(normalized_code))
                ).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, (normalized_email, _hash_key(normalized_code)))
                    row = cur.fetchone()
            if not row or row[3] is not None:
                raise TenantStoreError("login code is invalid or expired")
            expires_at = dt.datetime.fromisoformat(_time_text(row[2]) or "")
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=dt.timezone.utc)
            if expires_at <= now:
                raise TenantStoreError("login code is invalid or expired")
            if self.kind == "sqlite":
                updated = conn.execute(
                    "UPDATE web_login_codes SET consumed_at=? WHERE code_id=? AND consumed_at IS NULL",
                    (now.isoformat(), row[0]),
                ).rowcount
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE web_login_codes SET consumed_at=%s WHERE code_id=%s AND consumed_at IS NULL",
                        (now.isoformat(), row[0]),
                    )
                    updated = cur.rowcount
            if updated != 1:
                raise TenantStoreError("login code is invalid or expired")
            self._insert_audit(
                conn,
                str(row[1]),
                "web.login.succeeded",
                "web_login_code",
                str(row[0]),
                actor_type="web_auth",
            )
        return self.get(str(row[1]))

    def set_workspace_owner(
        self,
        tenant_id: str,
        email: str,
        *,
        actor_type: str = "admin_api",
        actor_id: str | None = None,
    ) -> str:
        """Set the verified owner email used to bind external identities."""
        normalized_email = email.strip().lower()
        if len(normalized_email) > 254 or not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email
        ):
            raise TenantStoreError("workspace owner email is invalid")
        self.get(tenant_id)
        now = _utcnow()
        with self._connect() as conn:
            if self.kind == "sqlite":
                conn.execute(
                    """INSERT INTO workspace_owners (tenant_id,email,created_at)
                       VALUES (?,?,?)
                       ON CONFLICT(tenant_id) DO UPDATE SET email=excluded.email""",
                    (tenant_id, normalized_email, now),
                )
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO workspace_owners (tenant_id,email,created_at)
                           VALUES (%s,%s,%s)
                           ON CONFLICT(tenant_id) DO UPDATE SET email=excluded.email""",
                        (tenant_id, normalized_email, now),
                    )
            self._insert_audit(
                conn,
                tenant_id,
                "workspace.owner.updated",
                "tenant",
                tenant_id,
                actor_type=actor_type,
                actor_id=actor_id,
                metadata={"owner_email": normalized_email},
            )
        return normalized_email

    def resolve_oauth_identity(self, issuer: str, subject: str) -> TenantRecord | None:
        """Resolve a verified OAuth subject to exactly one active tenant."""
        if not issuer or not subject:
            return None
        placeholder = "?" if self.kind == "sqlite" else "%s"
        active_predicate = "t.active=1" if self.kind == "sqlite" else "t.active=TRUE"
        sql = (
            "SELECT i.tenant_id FROM oauth_identities i "
            "JOIN tenants t ON t.tenant_id=i.tenant_id "
            f"WHERE i.issuer={placeholder} AND i.subject={placeholder} "
            f"AND {active_predicate}"
        )
        with self._connect() as conn:
            if self.kind == "sqlite":
                row = conn.execute(sql, (issuer, subject)).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, (issuer, subject))
                    row = cur.fetchone()
        return self.get(str(row[0])) if row else None

    def bind_oauth_identity(
        self,
        issuer: str,
        subject: str,
        verified_email: str,
    ) -> TenantRecord:
        """Bind an OAuth identity by an unambiguous verified owner email."""
        normalized_email = verified_email.strip().lower()
        if not issuer.startswith("https://") or len(issuer) > 500:
            raise TenantStoreError("OAuth issuer is invalid")
        if not subject or len(subject) > 500:
            raise TenantStoreError("OAuth subject is invalid")
        if len(normalized_email) > 254 or not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email
        ):
            raise TenantStoreError("verified OAuth email is invalid")

        existing = self.resolve_oauth_identity(issuer, subject)
        if existing is not None:
            return existing

        placeholder = "?" if self.kind == "sqlite" else "%s"
        active_predicate = "t.active=1" if self.kind == "sqlite" else "t.active=TRUE"
        owner_sql = (
            "SELECT o.tenant_id FROM workspace_owners o "
            "JOIN tenants t ON t.tenant_id=o.tenant_id "
            f"WHERE LOWER(o.email)={placeholder} AND {active_predicate}"
        )
        if self.kind == "postgres":
            owner_sql += " FOR UPDATE"
        now = _utcnow()
        try:
            with self._connect() as conn:
                if self.kind == "sqlite":
                    conn.execute("BEGIN IMMEDIATE")
                    rows = conn.execute(owner_sql, (normalized_email,)).fetchall()
                else:
                    with conn.cursor() as cur:
                        cur.execute(owner_sql, (normalized_email,))
                        rows = cur.fetchall()
                tenant_ids = sorted({str(row[0]) for row in rows})
                if not tenant_ids:
                    raise TenantStoreError(
                        "OAuth identity does not match a Harbor workspace owner"
                    )
                if len(tenant_ids) != 1:
                    raise TenantStoreError(
                        "OAuth identity matches more than one Harbor workspace"
                    )
                tenant_id = tenant_ids[0]
                values = (
                    issuer,
                    subject,
                    tenant_id,
                    normalized_email,
                    now,
                    now,
                )
                if self.kind == "sqlite":
                    conn.execute(
                        """INSERT INTO oauth_identities
                           (issuer,subject,tenant_id,email,created_at,last_seen_at)
                           VALUES (?,?,?,?,?,?)""",
                        values,
                    )
                else:
                    with conn.cursor() as cur:
                        cur.execute(
                            """INSERT INTO oauth_identities
                               (issuer,subject,tenant_id,email,created_at,last_seen_at)
                               VALUES (%s,%s,%s,%s,%s,%s)""",
                            values,
                        )
                self._insert_audit(
                    conn,
                    tenant_id,
                    "oauth.identity.bound",
                    "oauth_identity",
                    hashlib.sha256(f"{issuer}\0{subject}".encode()).hexdigest(),
                    actor_type="oauth",
                    metadata={"issuer": issuer, "owner_email": normalized_email},
                )
        except TenantStoreError:
            raise
        except Exception as error:
            resolved = self.resolve_oauth_identity(issuer, subject)
            if resolved is not None:
                return resolved
            raise TenantStoreError("OAuth identity could not be bound") from error
        return self.get(tenant_id)

    def get(self, tenant_id: str) -> TenantRecord:
        placeholder = "?" if self.kind == "sqlite" else "%s"
        sql = (
            "SELECT tenant_id,name,timezone,sprite_name,config_json,active "
            f"FROM tenants WHERE tenant_id = {placeholder}"
        )
        with self._connect() as conn:
            if self.kind == "sqlite":
                row = conn.execute(sql, (tenant_id,)).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, (tenant_id,))
                    row = cur.fetchone()
        if not row:
            raise TenantStoreError(f"unknown tenant '{tenant_id}'")
        config = json.loads(row[4]) if isinstance(row[4], str) else row[4]
        return TenantRecord(row[0], row[1], row[2], row[3], config, bool(row[5]))

    def list_active(self) -> list[TenantRecord]:
        predicate = "active = 1" if self.kind == "sqlite" else "active = TRUE"
        with self._connect() as conn:
            if self.kind == "sqlite":
                rows = conn.execute(
                    f"SELECT tenant_id FROM tenants WHERE {predicate}"
                ).fetchall()
            else:
                with conn.cursor() as cur:
                    cur.execute(f"SELECT tenant_id FROM tenants WHERE {predicate}")
                    rows = cur.fetchall()
        return [self.get(row[0]) for row in rows]

    def update_config(
        self,
        tenant_id: str,
        config: dict[str, Any],
        *,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> TenantRecord:
        validate_non_secret_metadata(config, "tenant.config")
        payload = json.dumps(config)
        now = _utcnow()
        with self._connect() as conn:
            if self.kind == "sqlite":
                cur = conn.execute(
                    "UPDATE tenants SET config_json=?,updated_at=? WHERE tenant_id=?",
                    (payload, now, tenant_id),
                )
                rowcount = cur.rowcount
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE tenants SET config_json=%s::jsonb,updated_at=%s WHERE tenant_id=%s",
                        (payload, now, tenant_id),
                    )
                    rowcount = cur.rowcount
            if rowcount != 1:
                raise TenantStoreError(f"unknown tenant '{tenant_id}'")
            self._insert_audit(
                conn,
                tenant_id,
                "tenant.config.updated",
                "tenant",
                tenant_id,
                actor_type=actor_type,
                actor_id=actor_id,
            )
        return self.get(tenant_id)

    def record_provisioning_status(
        self,
        tenant_id: str,
        status: str,
        *,
        error_type: str | None = None,
        actor_type: str = "system",
    ) -> TenantRecord:
        if status not in {"pending", "provisioning", "ready", "failed"}:
            raise TenantStoreError("provisioning status is invalid")
        record = self.get(tenant_id)
        config = dict(record.config)
        config["provisioning"] = {
            "status": status,
            "updated_at": _utcnow(),
            "error_type": error_type if status == "failed" else None,
        }
        updated = self.update_config(tenant_id, config, actor_type=actor_type)
        with self._connect() as conn:
            self._insert_audit(
                conn,
                tenant_id,
                f"tenant.provisioning.{status}",
                "sprite",
                record.sprite_name,
                actor_type=actor_type,
                metadata={"status": status, "error_type": error_type},
            )
        return updated

    def upsert_connection(
        self,
        tenant_id: str,
        connection: dict[str, Any],
        *,
        actor_type: str = "admin_api",
        actor_id: str | None = None,
    ) -> TenantRecord:
        validate_non_secret_metadata(connection, "connection")
        connection_id = connection.get("id")
        provider = connection.get("provider")
        if not connection_id or not provider:
            raise TenantStoreError("connection id and provider are required")

        placeholder = "?" if self.kind == "sqlite" else "%s"
        select_sql = f"SELECT config_json FROM tenants WHERE tenant_id={placeholder}"
        if self.kind == "postgres":
            select_sql += " FOR UPDATE"
        with self._connect() as conn:
            if self.kind == "sqlite":
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(select_sql, (tenant_id,)).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(select_sql, (tenant_id,))
                    row = cur.fetchone()
            if not row:
                raise TenantStoreError(f"unknown tenant '{tenant_id}'")
            config = json.loads(row[0]) if isinstance(row[0], str) else dict(row[0])
            connections = [
                item
                for item in config.get("connections", [])
                if item.get("id") != connection_id
            ]
            connections.append(connection)
            config["connections"] = connections
            payload = json.dumps(config)
            now = _utcnow()
            if self.kind == "sqlite":
                conn.execute(
                    "UPDATE tenants SET config_json=?,updated_at=? WHERE tenant_id=?",
                    (payload, now, tenant_id),
                )
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE tenants SET config_json=%s::jsonb,updated_at=%s WHERE tenant_id=%s",
                        (payload, now, tenant_id),
                    )
            self._insert_audit(
                conn,
                tenant_id,
                "connection.upserted",
                "connection",
                str(connection_id),
                actor_type=actor_type,
                actor_id=actor_id,
                metadata={"provider": provider},
            )
        return self.get(tenant_id)

    def update_worker_schedule(
        self,
        tenant_id: str,
        worker_id: str,
        schedule: dict[str, Any],
        timezone: str,
        next_run_at: str,
        *,
        actor_type: str = "tenant_api",
        actor_id: str | None = None,
    ) -> TenantRecord:
        validate_non_secret_metadata(schedule, "tenant.schedule")
        placeholder = "?" if self.kind == "sqlite" else "%s"
        select_sql = f"SELECT config_json FROM tenants WHERE tenant_id={placeholder}"
        if self.kind == "postgres":
            select_sql += " FOR UPDATE"
        with self._connect() as conn:
            if self.kind == "sqlite":
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(select_sql, (tenant_id,)).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(select_sql, (tenant_id,))
                    row = cur.fetchone()
            if not row:
                raise TenantStoreError(f"unknown tenant '{tenant_id}'")
            config = json.loads(row[0]) if isinstance(row[0], str) else dict(row[0])
            if worker_id not in config.get("workers", []):
                raise TenantStoreError(f"worker '{worker_id}' is not enabled")
            schedules = dict(config.get("schedule", {}))
            schedules[worker_id] = schedule
            config["schedule"] = schedules
            now = _utcnow()
            payload = json.dumps(config)
            if self.kind == "sqlite":
                conn.execute(
                    "UPDATE tenants SET timezone=?,config_json=?,updated_at=? WHERE tenant_id=?",
                    (timezone, payload, now, tenant_id),
                )
                latest = conn.execute(
                    """SELECT run_id,idempotency_key,status,attempt_count,last_error
                       FROM runs WHERE tenant_id=? AND worker_id=?
                         AND idempotency_key LIKE 'schedule-v1:%'
                       ORDER BY started_at DESC LIMIT 1""",
                    (tenant_id, worker_id),
                ).fetchone()
                state_values = (
                    tenant_id,
                    worker_id,
                    next_run_at,
                    latest[1] if latest else None,
                    latest[0] if latest else None,
                    latest[2] if latest else "scheduled",
                    int(latest[3]) if latest else 0,
                    latest[4] if latest else None,
                    now,
                )
                conn.execute(
                    """INSERT INTO schedule_state
                       (tenant_id,worker_id,next_run_at,last_window_key,last_run_id,
                        last_status,attempt_count,last_error,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(tenant_id,worker_id) DO UPDATE SET
                         next_run_at=excluded.next_run_at,
                         last_window_key=excluded.last_window_key,
                         last_run_id=excluded.last_run_id,
                         last_status=excluded.last_status,
                         attempt_count=excluded.attempt_count,
                         last_error=excluded.last_error,
                         updated_at=excluded.updated_at""",
                    state_values,
                )
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE tenants SET timezone=%s,config_json=%s::jsonb,updated_at=%s
                           WHERE tenant_id=%s""",
                        (timezone, payload, now, tenant_id),
                    )
                    cur.execute(
                        """SELECT run_id,idempotency_key,status,attempt_count,last_error
                           FROM runs WHERE tenant_id=%s AND worker_id=%s
                             AND idempotency_key LIKE 'schedule-v1:%%'
                           ORDER BY started_at DESC LIMIT 1""",
                        (tenant_id, worker_id),
                    )
                    latest = cur.fetchone()
                    state_values = (
                        tenant_id,
                        worker_id,
                        next_run_at,
                        latest[1] if latest else None,
                        latest[0] if latest else None,
                        latest[2] if latest else "scheduled",
                        int(latest[3]) if latest else 0,
                        latest[4] if latest else None,
                        now,
                    )
                    cur.execute(
                        """INSERT INTO schedule_state
                           (tenant_id,worker_id,next_run_at,last_window_key,last_run_id,
                            last_status,attempt_count,last_error,updated_at)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT(tenant_id,worker_id) DO UPDATE SET
                             next_run_at=EXCLUDED.next_run_at,
                             last_window_key=EXCLUDED.last_window_key,
                             last_run_id=EXCLUDED.last_run_id,
                             last_status=EXCLUDED.last_status,
                             attempt_count=EXCLUDED.attempt_count,
                             last_error=EXCLUDED.last_error,
                             updated_at=EXCLUDED.updated_at""",
                        state_values,
                    )
            self._insert_audit(
                conn,
                tenant_id,
                "schedule.configured",
                "worker",
                worker_id,
                actor_type=actor_type,
                actor_id=actor_id,
                metadata={"timezone": timezone, **schedule},
            )
        return self.get(tenant_id)

    def configure_email_output(
        self,
        tenant_id: str,
        *,
        enabled: bool,
        recipients: list[str],
        subject_prefix: str,
        actor_type: str = "tenant_api",
        actor_id: str | None = None,
    ) -> TenantRecord:
        email_settings = {
            "recipients": recipients,
            "subject_prefix": subject_prefix,
        }
        validate_non_secret_metadata(email_settings, "tenant.output_settings.email")
        placeholder = "?" if self.kind == "sqlite" else "%s"
        select_sql = f"SELECT config_json FROM tenants WHERE tenant_id={placeholder}"
        if self.kind == "postgres":
            select_sql += " FOR UPDATE"
        with self._connect() as conn:
            if self.kind == "sqlite":
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(select_sql, (tenant_id,)).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(select_sql, (tenant_id,))
                    row = cur.fetchone()
            if not row:
                raise TenantStoreError(f"unknown tenant '{tenant_id}'")
            config = json.loads(row[0]) if isinstance(row[0], str) else dict(row[0])
            outputs = [item for item in config.get("outputs", []) if item != "email"]
            output_settings = dict(config.get("output_settings") or {})
            if enabled:
                outputs.append("email")
                output_settings["email"] = email_settings
            else:
                output_settings.pop("email", None)
            config["outputs"] = outputs
            config["output_settings"] = output_settings
            payload = json.dumps(config)
            now = _utcnow()
            if self.kind == "sqlite":
                conn.execute(
                    "UPDATE tenants SET config_json=?,updated_at=? WHERE tenant_id=?",
                    (payload, now, tenant_id),
                )
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE tenants SET config_json=%s::jsonb,updated_at=%s WHERE tenant_id=%s",
                        (payload, now, tenant_id),
                    )
            self._insert_audit(
                conn,
                tenant_id,
                "output.email.configured" if enabled else "output.email.disabled",
                "output",
                "email",
                actor_type=actor_type,
                actor_id=actor_id,
                metadata={"enabled": enabled, "recipient_count": len(recipients)},
            )
        return self.get(tenant_id)

    def record_connection_verification(
        self,
        tenant_id: str,
        connection_id: str,
        result: dict[str, Any],
        *,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> TenantRecord:
        validate_non_secret_metadata(result, "connection.verification")
        status = result.get("status")
        if status not in {"verified", "failed"}:
            raise TenantStoreError("connection verification status is invalid")

        record = self.get(tenant_id)
        found = False
        connections = []
        for item in record.config.get("connections", []):
            connection = dict(item)
            if connection.get("id") == connection_id:
                found = True
                connection["status"] = status
                connection["last_verified_at"] = result.get("checked_at") or _utcnow()
                if status == "verified":
                    connection["last_error"] = None
                    connection["sync"] = {
                        "publication_id": result.get("publication_id"),
                        "publication_name": result.get("publication_name"),
                        "last_success_at": result.get("checked_at") or _utcnow(),
                    }
                else:
                    connection["last_error"] = result.get("error") or {
                        "kind": "connection_failed",
                        "detail": "connection verification failed",
                    }
            connections.append(connection)
        if not found:
            raise TenantStoreError(f"unknown connection '{connection_id}'")

        config = dict(record.config)
        config["connections"] = connections
        updated = self.update_config(
            tenant_id, config, actor_type=actor_type, actor_id=actor_id
        )
        with self._connect() as conn:
            self._insert_audit(
                conn,
                tenant_id,
                "connection.verified" if status == "verified" else "connection.failed",
                "connection",
                connection_id,
                actor_type=actor_type,
                actor_id=actor_id,
                metadata={"status": status},
            )
        return updated

    def set_sprite(
        self,
        tenant_id: str,
        sprite_name: str,
        *,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> None:
        now = _utcnow()
        with self._connect() as conn:
            if self.kind == "sqlite":
                cur = conn.execute(
                    "UPDATE tenants SET sprite_name=?,updated_at=? WHERE tenant_id=?",
                    (sprite_name, now, tenant_id),
                )
                rowcount = cur.rowcount
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE tenants SET sprite_name=%s,updated_at=%s WHERE tenant_id=%s",
                        (sprite_name, now, tenant_id),
                    )
                    rowcount = cur.rowcount
            if rowcount != 1:
                raise TenantStoreError(f"unknown tenant '{tenant_id}'")
            self._insert_audit(
                conn,
                tenant_id,
                "tenant.sprite.assigned",
                "sprite",
                sprite_name,
                actor_type=actor_type,
                actor_id=actor_id,
            )

    def set_active(self, tenant_id: str, active: bool) -> None:
        now = _utcnow()
        with self._connect() as conn:
            value = int(active) if self.kind == "sqlite" else active
            if self.kind == "sqlite":
                cur = conn.execute(
                    "UPDATE tenants SET active=?,updated_at=? WHERE tenant_id=?",
                    (value, now, tenant_id),
                )
                rowcount = cur.rowcount
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE tenants SET active=%s,updated_at=%s WHERE tenant_id=%s",
                        (value, now, tenant_id),
                    )
                    rowcount = cur.rowcount
            if rowcount != 1:
                raise TenantStoreError(f"unknown tenant '{tenant_id}'")
            self._insert_audit(
                conn,
                tenant_id,
                "tenant.activated" if active else "tenant.deactivated",
                "tenant",
                tenant_id,
            )

    def verify_api_key(self, tenant_id: str, candidate: str) -> bool:
        placeholder = "?" if self.kind == "sqlite" else "%s"
        active = "1" if self.kind == "sqlite" else "TRUE"
        sql = (
            f"SELECT api_key_hash FROM tenants "
            f"WHERE tenant_id={placeholder} AND active={active}"
        )
        with self._connect() as conn:
            if self.kind == "sqlite":
                row = conn.execute(sql, (tenant_id,)).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, (tenant_id,))
                    row = cur.fetchone()
        return bool(row and hmac.compare_digest(row[0], _hash_key(candidate)))

    def resolve_api_key(self, candidate: str) -> TenantRecord | None:
        """Resolve a bearer token to one active tenant without caller-supplied identity."""
        if not candidate:
            return None
        placeholder = "?" if self.kind == "sqlite" else "%s"
        active = "1" if self.kind == "sqlite" else "TRUE"
        sql = (
            "SELECT tenant_id FROM tenants "
            f"WHERE api_key_hash={placeholder} AND active={active}"
        )
        with self._connect() as conn:
            if self.kind == "sqlite":
                rows = conn.execute(sql, (_hash_key(candidate),)).fetchall()
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, (_hash_key(candidate),))
                    rows = cur.fetchall()
        return self.get(rows[0][0]) if len(rows) == 1 else None

    def claim_run(
        self,
        run_id: str,
        tenant_id: str,
        worker_id: str,
        idempotency_key: str,
        *,
        lease_seconds: int = 1800,
    ) -> bool:
        now = _utcnow()
        lease_expires_at = _lease_deadline(lease_seconds)
        try:
            with self._connect() as conn:
                values = (
                    run_id,
                    tenant_id,
                    worker_id,
                    idempotency_key,
                    "running",
                    now,
                    lease_expires_at,
                )
                if self.kind == "sqlite":
                    conn.execute(
                        """INSERT INTO runs
                           (run_id,tenant_id,worker_id,idempotency_key,status,started_at,
                            lease_expires_at)
                           VALUES (?,?,?,?,?,?,?)""",
                        values,
                    )
                else:
                    with conn.cursor() as cur:
                        cur.execute(
                            """INSERT INTO runs
                               (run_id,tenant_id,worker_id,idempotency_key,status,started_at,
                                lease_expires_at)
                               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                            values,
                        )
                self._insert_audit(
                    conn,
                    tenant_id,
                    "run.claimed",
                    "run",
                    run_id,
                    metadata={"worker_id": worker_id},
                )
            return True
        except sqlite3.IntegrityError as e:
            if "runs.tenant_id, runs.worker_id, runs.idempotency_key" in str(e):
                return False
            raise TenantStoreError(f"could not claim run '{run_id}': {e}") from e
        except Exception as e:
            if self.kind == "postgres":
                try:
                    from psycopg.errors import UniqueViolation  # type: ignore

                    if (
                        isinstance(e, UniqueViolation)
                        and getattr(e.diag, "constraint_name", None)
                        == "runs_tenant_worker_idempotency_uidx"
                    ):
                        return False
                except ImportError:
                    pass
            if isinstance(e, TenantStoreError):
                raise
            raise TenantStoreError(f"could not claim run '{run_id}': {e}") from e

    def reclaim_stale_run(self, run_id: str, *, lease_seconds: int = 1800) -> bool:
        now = _utcnow()
        lease_expires_at = _lease_deadline(lease_seconds)
        with self._connect() as conn:
            if self.kind == "sqlite":
                cur = conn.execute(
                    """UPDATE runs SET lease_expires_at=? WHERE run_id=?
                       AND status='running' AND lease_expires_at<=?""",
                    (lease_expires_at, run_id, now),
                )
                rowcount = cur.rowcount
                tenant_row = conn.execute(
                    "SELECT tenant_id FROM runs WHERE run_id=?", (run_id,)
                ).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE runs SET lease_expires_at=%s WHERE run_id=%s
                           AND status='running' AND lease_expires_at<=%s
                           RETURNING tenant_id""",
                        (lease_expires_at, run_id, now),
                    )
                    tenant_row = cur.fetchone()
                    rowcount = cur.rowcount
            if rowcount == 1 and tenant_row:
                self._insert_audit(
                    conn,
                    tenant_row[0],
                    "run.reclaimed",
                    "run",
                    run_id,
                )
                return True
        return False

    def begin_run_attempt(self, run_id: str, *, lease_seconds: int = 1800) -> int:
        lease_expires_at = _lease_deadline(lease_seconds)
        with self._connect() as conn:
            if self.kind == "sqlite":
                cur = conn.execute(
                    """UPDATE runs SET attempt_count=attempt_count+1,last_error=NULL,
                       lease_expires_at=? WHERE run_id=? AND status='running'""",
                    (lease_expires_at, run_id),
                )
                row = (
                    conn.execute(
                        "SELECT attempt_count FROM runs WHERE run_id=?", (run_id,)
                    ).fetchone()
                    if cur.rowcount == 1
                    else None
                )
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE runs SET attempt_count=attempt_count+1,last_error=NULL,
                           lease_expires_at=%s WHERE run_id=%s AND status='running'
                           RETURNING attempt_count""",
                        (lease_expires_at, run_id),
                    )
                    row = cur.fetchone()
        if not row:
            raise TenantStoreError(f"unknown run '{run_id}'")
        return int(row[0])

    def record_run_attempt_error(self, run_id: str, error: str) -> None:
        with self._connect() as conn:
            if self.kind == "sqlite":
                cur = conn.execute(
                    "UPDATE runs SET last_error=? WHERE run_id=?", (error, run_id)
                )
                rowcount = cur.rowcount
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE runs SET last_error=%s WHERE run_id=%s",
                        (error, run_id),
                    )
                    rowcount = cur.rowcount
        if rowcount != 1:
            raise TenantStoreError(f"unknown run '{run_id}'")

    def get_run_by_idempotency(
        self, tenant_id: str, worker_id: str, idempotency_key: str
    ) -> RunRecord | None:
        placeholders = ("?", "?", "?") if self.kind == "sqlite" else ("%s", "%s", "%s")
        sql = (
            "SELECT run_id,tenant_id,worker_id,idempotency_key,status,result_json,"
            "started_at,finished_at,attempt_count,last_error,lease_expires_at FROM runs WHERE "
            f"tenant_id={placeholders[0]} AND worker_id={placeholders[1]} "
            f"AND idempotency_key={placeholders[2]}"
        )
        with self._connect() as conn:
            if self.kind == "sqlite":
                row = conn.execute(
                    sql, (tenant_id, worker_id, idempotency_key)
                ).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, (tenant_id, worker_id, idempotency_key))
                    row = cur.fetchone()
        if not row:
            return None
        result = json.loads(row[5]) if isinstance(row[5], str) else row[5]
        return RunRecord(
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            result,
            _time_text(row[6]) or "",
            _time_text(row[7]),
            int(row[8]),
            row[9],
            _time_text(row[10]),
        )

    def list_runs(self, tenant_id: str, limit: int = 20) -> list[RunRecord]:
        if limit < 1 or limit > 100:
            raise TenantStoreError("run limit must be between 1 and 100")
        placeholders = ("?", "?") if self.kind == "sqlite" else ("%s", "%s")
        sql = (
            "SELECT run_id,tenant_id,worker_id,idempotency_key,status,result_json,"
            "started_at,finished_at,attempt_count,last_error,lease_expires_at "
            f"FROM runs WHERE tenant_id={placeholders[0]} "
            f"ORDER BY started_at DESC LIMIT {placeholders[1]}"
        )
        with self._connect() as conn:
            if self.kind == "sqlite":
                rows = conn.execute(sql, (tenant_id, limit)).fetchall()
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, (tenant_id, limit))
                    rows = cur.fetchall()
        records = []
        for row in rows:
            result = json.loads(row[5]) if isinstance(row[5], str) else row[5]
            records.append(
                RunRecord(
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    result,
                    _time_text(row[6]) or "",
                    _time_text(row[7]),
                    int(row[8]),
                    row[9],
                    _time_text(row[10]),
                )
            )
        return records

    def get_schedule_state(
        self, tenant_id: str, worker_id: str
    ) -> ScheduleState | None:
        placeholders = ("?", "?") if self.kind == "sqlite" else ("%s", "%s")
        sql = (
            "SELECT tenant_id,worker_id,next_run_at,last_window_key,last_run_id,"
            "last_status,attempt_count,last_error,updated_at FROM schedule_state "
            f"WHERE tenant_id={placeholders[0]} AND worker_id={placeholders[1]}"
        )
        with self._connect() as conn:
            if self.kind == "sqlite":
                row = conn.execute(sql, (tenant_id, worker_id)).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, (tenant_id, worker_id))
                    row = cur.fetchone()
        if not row:
            return None
        return ScheduleState(
            row[0],
            row[1],
            _time_text(row[2]) or "",
            row[3],
            row[4],
            row[5],
            int(row[6]),
            row[7],
            _time_text(row[8]) or "",
        )

    def upsert_schedule_state(
        self,
        tenant_id: str,
        worker_id: str,
        *,
        next_run_at: str,
        last_window_key: str | None = None,
        last_run_id: str | None = None,
        last_status: str,
        attempt_count: int = 0,
        last_error: str | None = None,
    ) -> ScheduleState:
        now = _utcnow()
        values = (
            tenant_id,
            worker_id,
            next_run_at,
            last_window_key,
            last_run_id,
            last_status,
            attempt_count,
            last_error,
            now,
        )
        with self._connect() as conn:
            if self.kind == "sqlite":
                conn.execute(
                    """INSERT INTO schedule_state
                       (tenant_id,worker_id,next_run_at,last_window_key,last_run_id,
                        last_status,attempt_count,last_error,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(tenant_id,worker_id) DO UPDATE SET
                         next_run_at=excluded.next_run_at,
                         last_window_key=excluded.last_window_key,
                         last_run_id=excluded.last_run_id,
                         last_status=excluded.last_status,
                         attempt_count=excluded.attempt_count,
                         last_error=excluded.last_error,
                         updated_at=excluded.updated_at""",
                    values,
                )
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO schedule_state
                           (tenant_id,worker_id,next_run_at,last_window_key,last_run_id,
                            last_status,attempt_count,last_error,updated_at)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT(tenant_id,worker_id) DO UPDATE SET
                             next_run_at=EXCLUDED.next_run_at,
                             last_window_key=EXCLUDED.last_window_key,
                             last_run_id=EXCLUDED.last_run_id,
                             last_status=EXCLUDED.last_status,
                             attempt_count=EXCLUDED.attempt_count,
                             last_error=EXCLUDED.last_error,
                             updated_at=EXCLUDED.updated_at""",
                        values,
                    )
            self._insert_audit(
                conn,
                tenant_id,
                "schedule.state.updated",
                "worker",
                worker_id,
                metadata={"status": last_status},
            )
        state = self.get_schedule_state(tenant_id, worker_id)
        if state is None:  # pragma: no cover - defensive after successful upsert
            raise TenantStoreError("schedule state was not persisted")
        return state

    def upsert_service_heartbeat(
        self,
        service_id: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> ServiceHeartbeat:
        if not re.fullmatch(r"[a-z][a-z0-9._-]{0,63}", service_id):
            raise TenantStoreError("service heartbeat id is invalid")
        if status not in {"starting", "running", "healthy", "degraded", "failed"}:
            raise TenantStoreError("service heartbeat status is invalid")
        metadata = metadata or {}
        validate_non_secret_metadata(metadata, "service_heartbeat.metadata")
        now = _utcnow()
        payload = json.dumps(metadata)
        with self._connect() as conn:
            if self.kind == "sqlite":
                conn.execute(
                    """INSERT INTO service_heartbeats
                       (service_id,status,metadata_json,updated_at) VALUES (?,?,?,?)
                       ON CONFLICT(service_id) DO UPDATE SET
                         status=excluded.status,
                         metadata_json=excluded.metadata_json,
                         updated_at=excluded.updated_at""",
                    (service_id, status, payload, now),
                )
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO service_heartbeats
                           (service_id,status,metadata_json,updated_at)
                           VALUES (%s,%s,%s::jsonb,%s)
                           ON CONFLICT(service_id) DO UPDATE SET
                             status=EXCLUDED.status,
                             metadata_json=EXCLUDED.metadata_json,
                             updated_at=EXCLUDED.updated_at""",
                        (service_id, status, payload, now),
                    )
        heartbeat = self.get_service_heartbeat(service_id)
        if heartbeat is None:  # pragma: no cover - defensive after successful upsert
            raise TenantStoreError("service heartbeat was not persisted")
        return heartbeat

    def get_service_heartbeat(self, service_id: str) -> ServiceHeartbeat | None:
        placeholder = "?" if self.kind == "sqlite" else "%s"
        sql = (
            "SELECT service_id,status,metadata_json,updated_at "
            f"FROM service_heartbeats WHERE service_id={placeholder}"
        )
        with self._connect() as conn:
            if self.kind == "sqlite":
                row = conn.execute(sql, (service_id,)).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, (service_id,))
                    row = cur.fetchone()
        if not row:
            return None
        metadata = json.loads(row[2]) if isinstance(row[2], str) else dict(row[2])
        return ServiceHeartbeat(
            service_id=row[0],
            status=row[1],
            metadata=metadata,
            updated_at=_time_text(row[3]) or "",
        )

    def operational_snapshot(
        self,
        now: dt.datetime | None = None,
        *,
        overdue_grace_seconds: int = 900,
    ) -> dict[str, Any]:
        """Return aggregate, non-tenant-identifying state for health metrics."""
        now = now or dt.datetime.now(dt.timezone.utc)
        if now.tzinfo is None:
            raise TenantStoreError("operational snapshot time must be timezone-aware")
        if overdue_grace_seconds < 0 or overdue_grace_seconds > 86_400:
            raise TenantStoreError("operational snapshot grace period is invalid")
        now = now.astimezone(dt.timezone.utc)
        overdue_before = now - dt.timedelta(seconds=overdue_grace_seconds)
        active_predicate = "active=1" if self.kind == "sqlite" else "active=TRUE"
        with self._connect() as conn:
            if self.kind == "sqlite":
                active_tenants = int(
                    conn.execute(
                        f"SELECT COUNT(*) FROM tenants WHERE {active_predicate}"
                    ).fetchone()[0]
                )
                run_rows = conn.execute(
                    "SELECT status,COUNT(*) FROM runs GROUP BY status"
                ).fetchall()
                delivery_rows = conn.execute(
                    "SELECT status,COUNT(*) FROM deliveries GROUP BY status"
                ).fetchall()
                schedule_rows = conn.execute(
                    "SELECT next_run_at,last_status FROM schedule_state"
                ).fetchall()
                lease_rows = conn.execute(
                    "SELECT lease_expires_at FROM runs WHERE status='running'"
                ).fetchall()
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT COUNT(*) FROM tenants WHERE {active_predicate}"
                    )
                    active_tenants = int(cur.fetchone()[0])
                    cur.execute("SELECT status,COUNT(*) FROM runs GROUP BY status")
                    run_rows = cur.fetchall()
                    cur.execute(
                        "SELECT status,COUNT(*) FROM deliveries GROUP BY status"
                    )
                    delivery_rows = cur.fetchall()
                    cur.execute("SELECT next_run_at,last_status FROM schedule_state")
                    schedule_rows = cur.fetchall()
                    cur.execute(
                        "SELECT lease_expires_at FROM runs WHERE status='running'"
                    )
                    lease_rows = cur.fetchall()

        def parsed(value: Any) -> dt.datetime:
            result = dt.datetime.fromisoformat(_time_text(value) or "")
            if result.tzinfo is None:
                result = result.replace(tzinfo=dt.timezone.utc)
            return result.astimezone(dt.timezone.utc)

        overdue_schedules = sum(
            1
            for next_run_at, last_status in schedule_rows
            if last_status not in {"running"} and parsed(next_run_at) < overdue_before
        )
        expired_run_leases = sum(
            1
            for (lease_expires_at,) in lease_rows
            if lease_expires_at is not None and parsed(lease_expires_at) < now
        )
        heartbeat = self.get_service_heartbeat("scheduler")
        heartbeat_age = None
        if heartbeat is not None:
            heartbeat_age = max(
                0.0, (now - parsed(heartbeat.updated_at)).total_seconds()
            )
        return {
            "schema_version": self.schema_version,
            "active_tenants": active_tenants,
            "runs": {str(row[0]): int(row[1]) for row in run_rows},
            "deliveries": {str(row[0]): int(row[1]) for row in delivery_rows},
            "overdue_schedules": overdue_schedules,
            "expired_run_leases": expired_run_leases,
            "scheduler_heartbeat_status": heartbeat.status if heartbeat else "missing",
            "scheduler_heartbeat_age_seconds": heartbeat_age,
        }

    def get_billing(self, tenant_id: str) -> BillingRecord | None:
        placeholder = "?" if self.kind == "sqlite" else "%s"
        sql = (
            "SELECT tenant_id,plan,source_limit,api_access,status,stripe_customer_id,"
            "stripe_subscription_id,current_period_end,updated_at "
            f"FROM billing_accounts WHERE tenant_id={placeholder}"
        )
        with self._connect() as conn:
            if self.kind == "sqlite":
                row = conn.execute(sql, (tenant_id,)).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, (tenant_id,))
                    row = cur.fetchone()
        if not row:
            return None
        return BillingRecord(
            tenant_id=str(row[0]),
            plan=str(row[1]),
            source_limit=int(row[2]),
            api_access=bool(row[3]),
            status=str(row[4]),
            stripe_customer_id=str(row[5]) if row[5] else None,
            stripe_subscription_id=str(row[6]) if row[6] else None,
            current_period_end=_time_text(row[7]),
            updated_at=_time_text(row[8]) or "",
        )

    def billing_tenant_for_customer(self, customer_id: str) -> str | None:
        placeholder = "?" if self.kind == "sqlite" else "%s"
        sql = f"SELECT tenant_id FROM billing_accounts WHERE stripe_customer_id={placeholder}"
        with self._connect() as conn:
            if self.kind == "sqlite":
                row = conn.execute(sql, (customer_id,)).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, (customer_id,))
                    row = cur.fetchone()
        return str(row[0]) if row else None

    def apply_billing_event(
        self,
        event_id: str,
        event_type: str,
        tenant_id: str,
        *,
        plan: str,
        source_limit: int,
        api_access: bool,
        status: str,
        stripe_customer_id: str | None,
        stripe_subscription_id: str | None,
        current_period_end: str | None = None,
    ) -> bool:
        """Apply one verified Stripe event exactly once and update entitlements."""
        if not re.fullmatch(r"evt_[A-Za-z0-9_]+", event_id):
            raise TenantStoreError("billing event id is invalid")
        if not re.fullmatch(r"[a-z0-9._-]{2,64}", plan):
            raise TenantStoreError("billing plan is invalid")
        if source_limit < 1 or source_limit > 100:
            raise TenantStoreError("billing source limit is invalid")
        if status not in {
            "pending",
            "trialing",
            "active",
            "past_due",
            "canceled",
            "unpaid",
            "paused",
            "incomplete",
            "incomplete_expired",
        }:
            raise TenantStoreError("billing status is invalid")
        for value, label in (
            (stripe_customer_id, "customer"),
            (stripe_subscription_id, "subscription"),
        ):
            if value is not None and not re.fullmatch(r"[A-Za-z0-9_]+", value):
                raise TenantStoreError(f"Stripe {label} id is invalid")
        now = _utcnow()
        values = (
            tenant_id,
            plan,
            source_limit,
            api_access,
            status,
            stripe_customer_id,
            stripe_subscription_id,
            current_period_end,
            now,
        )
        try:
            with self._connect() as conn:
                if self.kind == "sqlite":
                    conn.execute("BEGIN IMMEDIATE")
                    if conn.execute(
                        "SELECT 1 FROM billing_events WHERE event_id=?", (event_id,)
                    ).fetchone():
                        return False
                    conn.execute(
                        """INSERT INTO billing_accounts
                           (tenant_id,plan,source_limit,api_access,status,stripe_customer_id,
                            stripe_subscription_id,current_period_end,updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?)
                           ON CONFLICT(tenant_id) DO UPDATE SET
                             plan=excluded.plan,source_limit=excluded.source_limit,
                             api_access=excluded.api_access,status=excluded.status,
                             stripe_customer_id=COALESCE(excluded.stripe_customer_id,billing_accounts.stripe_customer_id),
                             stripe_subscription_id=COALESCE(excluded.stripe_subscription_id,billing_accounts.stripe_subscription_id),
                             current_period_end=excluded.current_period_end,updated_at=excluded.updated_at""",
                        values,
                    )
                    conn.execute(
                        "INSERT INTO billing_events (event_id,tenant_id,event_type,processed_at) VALUES (?,?,?,?)",
                        (event_id, tenant_id, event_type, now),
                    )
                else:
                    with conn.cursor() as cur:
                        cur.execute(
                            """INSERT INTO billing_events
                               (event_id,tenant_id,event_type,processed_at)
                               VALUES (%s,%s,%s,%s)
                               ON CONFLICT(event_id) DO NOTHING
                               RETURNING event_id""",
                            (event_id, tenant_id, event_type, now),
                        )
                        if cur.fetchone() is None:
                            return False
                        cur.execute(
                            """INSERT INTO billing_accounts
                               (tenant_id,plan,source_limit,api_access,status,stripe_customer_id,
                                stripe_subscription_id,current_period_end,updated_at)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                               ON CONFLICT(tenant_id) DO UPDATE SET
                                 plan=EXCLUDED.plan,source_limit=EXCLUDED.source_limit,
                                 api_access=EXCLUDED.api_access,status=EXCLUDED.status,
                                 stripe_customer_id=COALESCE(EXCLUDED.stripe_customer_id,billing_accounts.stripe_customer_id),
                                 stripe_subscription_id=COALESCE(EXCLUDED.stripe_subscription_id,billing_accounts.stripe_subscription_id),
                                 current_period_end=EXCLUDED.current_period_end,updated_at=EXCLUDED.updated_at""",
                            values,
                        )
                self._insert_audit(
                    conn,
                    tenant_id,
                    "billing.updated",
                    "subscription",
                    stripe_subscription_id,
                    actor_type="stripe_webhook",
                    metadata={"plan": plan, "status": status, "event_type": event_type},
                )
            return True
        except TenantStoreError:
            raise
        except Exception as error:
            raise TenantStoreError("billing event could not be applied") from error

    def claim_delivery(
        self,
        delivery_id: str,
        tenant_id: str,
        run_id: str,
        adapter: str,
        destination_fingerprint: str,
        idempotency_key: str,
    ) -> bool:
        now = _utcnow()
        values = (
            delivery_id,
            tenant_id,
            run_id,
            adapter,
            destination_fingerprint,
            idempotency_key,
            "pending",
            now,
            now,
        )
        try:
            with self._connect() as conn:
                if self.kind == "sqlite":
                    conn.execute(
                        """INSERT INTO deliveries
                           (delivery_id,tenant_id,run_id,adapter,destination_fingerprint,
                            idempotency_key,status,created_at,updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        values,
                    )
                else:
                    with conn.cursor() as cur:
                        cur.execute(
                            """INSERT INTO deliveries
                               (delivery_id,tenant_id,run_id,adapter,destination_fingerprint,
                                idempotency_key,status,created_at,updated_at)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            values,
                        )
                self._insert_audit(
                    conn,
                    tenant_id,
                    "delivery.claimed",
                    "delivery",
                    delivery_id,
                    metadata={"adapter": adapter, "run_id": run_id},
                )
            return True
        except sqlite3.IntegrityError as error:
            if (
                "deliveries.tenant_id, deliveries.adapter, deliveries.idempotency_key"
                in str(error)
            ):
                return False
            raise TenantStoreError(
                f"could not claim delivery '{delivery_id}': {error}"
            ) from error
        except Exception as error:
            if self.kind == "postgres":
                try:
                    from psycopg.errors import UniqueViolation  # type: ignore

                    if (
                        isinstance(error, UniqueViolation)
                        and getattr(error.diag, "constraint_name", None)
                        == "deliveries_tenant_adapter_idempotency_uidx"
                    ):
                        return False
                except ImportError:
                    pass
            if isinstance(error, TenantStoreError):
                raise
            raise TenantStoreError(
                f"could not claim delivery '{delivery_id}': {error}"
            ) from error

    def _delivery_from_row(self, row: Any) -> DeliveryRecord:
        return DeliveryRecord(
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
            row[6],
            row[7],
            int(row[8]),
            row[9],
            _time_text(row[10]) or "",
            _time_text(row[11]) or "",
            _time_text(row[12]),
        )

    def get_delivery_by_idempotency(
        self, tenant_id: str, adapter: str, idempotency_key: str
    ) -> DeliveryRecord | None:
        placeholders = ("?", "?", "?") if self.kind == "sqlite" else ("%s", "%s", "%s")
        sql = (
            "SELECT delivery_id,tenant_id,run_id,adapter,destination_fingerprint,"
            "idempotency_key,status,provider_message_id,attempt_count,last_error,"
            "created_at,updated_at,delivered_at FROM deliveries WHERE "
            f"tenant_id={placeholders[0]} AND adapter={placeholders[1]} "
            f"AND idempotency_key={placeholders[2]}"
        )
        with self._connect() as conn:
            if self.kind == "sqlite":
                row = conn.execute(
                    sql, (tenant_id, adapter, idempotency_key)
                ).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, (tenant_id, adapter, idempotency_key))
                    row = cur.fetchone()
        return self._delivery_from_row(row) if row else None

    def get_delivery(self, delivery_id: str) -> DeliveryRecord:
        placeholder = "?" if self.kind == "sqlite" else "%s"
        sql = (
            "SELECT delivery_id,tenant_id,run_id,adapter,destination_fingerprint,"
            "idempotency_key,status,provider_message_id,attempt_count,last_error,"
            f"created_at,updated_at,delivered_at FROM deliveries WHERE delivery_id={placeholder}"
        )
        with self._connect() as conn:
            if self.kind == "sqlite":
                row = conn.execute(sql, (delivery_id,)).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, (delivery_id,))
                    row = cur.fetchone()
        if not row:
            raise TenantStoreError(f"unknown delivery '{delivery_id}'")
        return self._delivery_from_row(row)

    def begin_delivery_attempt(self, delivery_id: str) -> int:
        now = _utcnow()
        with self._connect() as conn:
            if self.kind == "sqlite":
                conn.execute(
                    """UPDATE deliveries SET status='delivering',
                       attempt_count=attempt_count+1,last_error=NULL,updated_at=?
                       WHERE delivery_id=?""",
                    (now, delivery_id),
                )
                row = conn.execute(
                    "SELECT attempt_count FROM deliveries WHERE delivery_id=?",
                    (delivery_id,),
                ).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE deliveries SET status='delivering',
                           attempt_count=attempt_count+1,last_error=NULL,updated_at=%s
                           WHERE delivery_id=%s RETURNING attempt_count""",
                        (now, delivery_id),
                    )
                    row = cur.fetchone()
        if not row:
            raise TenantStoreError(f"unknown delivery '{delivery_id}'")
        return int(row[0])

    def finish_delivery(
        self,
        delivery_id: str,
        status: str,
        *,
        provider_message_id: str | None = None,
        last_error: str | None = None,
    ) -> DeliveryRecord:
        if status not in {"delivered", "failed"}:
            raise TenantStoreError("delivery status must be delivered or failed")
        if provider_message_id is not None and len(provider_message_id) > 255:
            raise TenantStoreError("provider message id is too long")
        now = _utcnow()
        delivered_at = now if status == "delivered" else None
        values = (
            status,
            provider_message_id,
            last_error,
            now,
            delivered_at,
            delivery_id,
        )
        with self._connect() as conn:
            if self.kind == "sqlite":
                cur = conn.execute(
                    """UPDATE deliveries SET status=?,provider_message_id=?,last_error=?,
                       updated_at=?,delivered_at=? WHERE delivery_id=?""",
                    values,
                )
                rowcount = cur.rowcount
                tenant_row = conn.execute(
                    "SELECT tenant_id FROM deliveries WHERE delivery_id=?",
                    (delivery_id,),
                ).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE deliveries SET status=%s,provider_message_id=%s,last_error=%s,
                           updated_at=%s,delivered_at=%s WHERE delivery_id=%s
                           RETURNING tenant_id""",
                        values,
                    )
                    tenant_row = cur.fetchone()
                    rowcount = cur.rowcount
            if rowcount != 1 or not tenant_row:
                raise TenantStoreError(f"unknown delivery '{delivery_id}'")
            self._insert_audit(
                conn,
                tenant_row[0],
                "delivery.finished",
                "delivery",
                delivery_id,
                metadata={"status": status},
            )
        return self.get_delivery(delivery_id)

    def finish_run(self, run_id: str, status: str, result: dict[str, Any]) -> None:
        now = _utcnow()
        payload = json.dumps(result)
        with self._connect() as conn:
            if self.kind == "sqlite":
                cur = conn.execute(
                    """UPDATE runs SET status=?,result_json=?,finished_at=?,
                       lease_expires_at=NULL WHERE run_id=?""",
                    (status, payload, now, run_id),
                )
                rowcount = cur.rowcount
                tenant_row = conn.execute(
                    "SELECT tenant_id FROM runs WHERE run_id=?", (run_id,)
                ).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE runs
                           SET status=%s,result_json=%s::jsonb,finished_at=%s,
                               lease_expires_at=NULL
                           WHERE run_id=%s RETURNING tenant_id""",
                        (status, payload, now, run_id),
                    )
                    tenant_row = cur.fetchone()
                    rowcount = cur.rowcount
            if rowcount != 1 or not tenant_row:
                raise TenantStoreError(f"unknown run '{run_id}'")
            self._insert_audit(
                conn,
                tenant_row[0],
                "run.finished",
                "run",
                run_id,
                metadata={"status": status},
            )

    def list_audit(self, tenant_id: str, limit: int = 100) -> list[AuditRecord]:
        if limit < 1 or limit > 500:
            raise TenantStoreError("audit limit must be between 1 and 500")
        sql = (
            "SELECT audit_id,tenant_id,actor_type,actor_id,action,"
            "target_type,target_id,metadata_json,created_at "
            + (
                "FROM audit_log WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?"
                if self.kind == "sqlite"
                else "FROM audit_log WHERE tenant_id=%s ORDER BY created_at DESC LIMIT %s"
            )
        )
        with self._connect() as conn:
            if self.kind == "sqlite":
                rows = conn.execute(sql, (tenant_id, limit)).fetchall()
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, (tenant_id, limit))
                    rows = cur.fetchall()
        records = []
        for row in rows:
            metadata = json.loads(row[7]) if isinstance(row[7], str) else row[7]
            created_at = (
                row[8].isoformat() if hasattr(row[8], "isoformat") else str(row[8])
            )
            records.append(AuditRecord(*row[:7], metadata, created_at))
        return records
