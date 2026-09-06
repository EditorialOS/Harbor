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


LATEST_SCHEMA_VERSION = 4

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
                conn.execute(
                    "DELETE FROM schedule_state WHERE tenant_id=? AND worker_id=?",
                    (tenant_id, worker_id),
                )
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE tenants SET timezone=%s,config_json=%s::jsonb,updated_at=%s
                           WHERE tenant_id=%s""",
                        (timezone, payload, now, tenant_id),
                    )
                    cur.execute(
                        "DELETE FROM schedule_state WHERE tenant_id=%s AND worker_id=%s",
                        (tenant_id, worker_id),
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

    def claim_run(
        self,
        run_id: str,
        tenant_id: str,
        worker_id: str,
        idempotency_key: str,
    ) -> bool:
        now = _utcnow()
        try:
            with self._connect() as conn:
                values = (
                    run_id,
                    tenant_id,
                    worker_id,
                    idempotency_key,
                    "running",
                    now,
                )
                if self.kind == "sqlite":
                    conn.execute(
                        """INSERT INTO runs
                           (run_id,tenant_id,worker_id,idempotency_key,status,started_at)
                           VALUES (?,?,?,?,?,?)""",
                        values,
                    )
                else:
                    with conn.cursor() as cur:
                        cur.execute(
                            """INSERT INTO runs
                               (run_id,tenant_id,worker_id,idempotency_key,status,started_at)
                               VALUES (%s,%s,%s,%s,%s,%s)""",
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

    def begin_run_attempt(self, run_id: str) -> int:
        with self._connect() as conn:
            if self.kind == "sqlite":
                conn.execute(
                    "UPDATE runs SET attempt_count=attempt_count+1,last_error=NULL WHERE run_id=?",
                    (run_id,),
                )
                row = conn.execute(
                    "SELECT attempt_count FROM runs WHERE run_id=?", (run_id,)
                ).fetchone()
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE runs SET attempt_count=attempt_count+1,last_error=NULL
                           WHERE run_id=%s RETURNING attempt_count""",
                        (run_id,),
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
            "started_at,finished_at,attempt_count,last_error FROM runs WHERE "
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
        )

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

    def finish_run(self, run_id: str, status: str, result: dict[str, Any]) -> None:
        now = _utcnow()
        payload = json.dumps(result)
        with self._connect() as conn:
            if self.kind == "sqlite":
                cur = conn.execute(
                    "UPDATE runs SET status=?,result_json=?,finished_at=? WHERE run_id=?",
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
                           SET status=%s,result_json=%s::jsonb,finished_at=%s
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
