"""Tenant and run state for Harbor's control plane.

SQLite is supported for local development. Production uses Postgres via
DATABASE_URL. Tenant JSON contains metadata only: publication ids, connector ids,
worker settings, schedule, and Sprite name. It must never contain provider
credentials.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from typing import Any, Iterable


class TenantStoreError(RuntimeError):
    pass


@dataclass
class TenantRecord:
    tenant_id: str
    name: str
    timezone: str
    sprite_name: str | None
    config: dict[str, Any]
    active: bool = True


SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS tenants (
    tenant_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    timezone TEXT NOT NULL,
    sprite_name TEXT,
    api_key_hash TEXT NOT NULL,
    config_json TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    worker_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    result_json TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);
"""


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def issue_tenant_key() -> str:
    return "harbor_" + secrets.token_urlsafe(32)


class TenantStore:
    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or os.environ.get("DATABASE_URL") or "sqlite:///harbor.db"
        self.kind = "postgres" if self.database_url.startswith(("postgres://", "postgresql://")) else "sqlite"
        self._init_schema()

    def _sqlite_path(self) -> str:
        if not self.database_url.startswith("sqlite:///"):
            raise TenantStoreError("unsupported SQLite URL; use sqlite:///path")
        return self.database_url.removeprefix("sqlite:///")

    def _connect(self):
        if self.kind == "sqlite":
            conn = sqlite3.connect(self._sqlite_path())
            conn.row_factory = sqlite3.Row
            return conn
        try:
            import psycopg  # type: ignore
        except ImportError as e:
            raise TenantStoreError("Install psycopg[binary] for Postgres production") from e
        return psycopg.connect(self.database_url)

    def _init_schema(self) -> None:
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        if self.kind == "sqlite":
            with self._connect() as conn:
                conn.executescript(SCHEMA_SQLITE)
            return
        statements = [
            """CREATE TABLE IF NOT EXISTS tenants (
                tenant_id TEXT PRIMARY KEY, name TEXT NOT NULL, timezone TEXT NOT NULL,
                sprite_name TEXT, api_key_hash TEXT NOT NULL, config_json JSONB NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                worker_id TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL, result_json JSONB, started_at TIMESTAMPTZ NOT NULL,
                finished_at TIMESTAMPTZ)""",
        ]
        with self._connect() as conn:
            with conn.cursor() as cur:
                for stmt in statements:
                    cur.execute(stmt)
            conn.commit()

    def create_tenant(self, tenant_id: str, name: str, timezone: str, config: dict[str, Any]) -> tuple[TenantRecord, str]:
        api_key = issue_tenant_key()
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        payload = json.dumps(config)
        if self.kind == "sqlite":
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO tenants (tenant_id,name,timezone,sprite_name,api_key_hash,config_json,active,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (tenant_id, name, timezone, None, _hash_key(api_key), payload, 1, now, now),
                )
        else:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO tenants (tenant_id,name,timezone,sprite_name,api_key_hash,config_json,active,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)",
                        (tenant_id, name, timezone, None, _hash_key(api_key), payload, True, now, now),
                    )
                conn.commit()
        return self.get(tenant_id), api_key

    def get(self, tenant_id: str) -> TenantRecord:
        sql = "SELECT tenant_id,name,timezone,sprite_name,config_json,active FROM tenants WHERE tenant_id = ?" if self.kind == "sqlite" else "SELECT tenant_id,name,timezone,sprite_name,config_json,active FROM tenants WHERE tenant_id = %s"
        with self._connect() as conn:
            cur = conn.execute(sql, (tenant_id,)) if self.kind == "sqlite" else conn.cursor()
            if self.kind != "sqlite":
                cur.execute(sql, (tenant_id,))
            row = cur.fetchone()
        if not row:
            raise TenantStoreError(f"unknown tenant '{tenant_id}'")
        config = row[4]
        if isinstance(config, str):
            config = json.loads(config)
        return TenantRecord(row[0], row[1], row[2], row[3], config, bool(row[5]))

    def list_active(self) -> list[TenantRecord]:
        sql = "SELECT tenant_id FROM tenants WHERE active = 1" if self.kind == "sqlite" else "SELECT tenant_id FROM tenants WHERE active = TRUE"
        with self._connect() as conn:
            cur = conn.execute(sql) if self.kind == "sqlite" else conn.cursor()
            if self.kind != "sqlite":
                cur.execute(sql)
            ids = [r[0] for r in cur.fetchall()]
        return [self.get(i) for i in ids]

    def set_sprite(self, tenant_id: str, sprite_name: str) -> None:
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        sql = "UPDATE tenants SET sprite_name=?,updated_at=? WHERE tenant_id=?" if self.kind == "sqlite" else "UPDATE tenants SET sprite_name=%s,updated_at=%s WHERE tenant_id=%s"
        with self._connect() as conn:
            if self.kind == "sqlite":
                conn.execute(sql, (sprite_name, now, tenant_id))
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, (sprite_name, now, tenant_id))
                conn.commit()

    def verify_api_key(self, tenant_id: str, candidate: str) -> bool:
        sql = "SELECT api_key_hash FROM tenants WHERE tenant_id=?" if self.kind == "sqlite" else "SELECT api_key_hash FROM tenants WHERE tenant_id=%s"
        with self._connect() as conn:
            cur = conn.execute(sql, (tenant_id,)) if self.kind == "sqlite" else conn.cursor()
            if self.kind != "sqlite":
                cur.execute(sql, (tenant_id,))
            row = cur.fetchone()
        return bool(row and hmac.compare_digest(row[0], _hash_key(candidate)))

    def claim_run(self, run_id: str, tenant_id: str, worker_id: str, idempotency_key: str) -> bool:
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        try:
            if self.kind == "sqlite":
                with self._connect() as conn:
                    conn.execute("INSERT INTO runs (run_id,tenant_id,worker_id,idempotency_key,status,started_at) VALUES (?,?,?,?,?,?)", (run_id,tenant_id,worker_id,idempotency_key,"running",now))
            else:
                with self._connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute("INSERT INTO runs (run_id,tenant_id,worker_id,idempotency_key,status,started_at) VALUES (%s,%s,%s,%s,%s,%s)", (run_id,tenant_id,worker_id,idempotency_key,"running",now))
                    conn.commit()
            return True
        except Exception:
            return False

    def finish_run(self, run_id: str, status: str, result: dict[str, Any]) -> None:
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        payload = json.dumps(result)
        sql = "UPDATE runs SET status=?,result_json=?,finished_at=? WHERE run_id=?" if self.kind == "sqlite" else "UPDATE runs SET status=%s,result_json=%s::jsonb,finished_at=%s WHERE run_id=%s"
        with self._connect() as conn:
            if self.kind == "sqlite":
                conn.execute(sql, (status, payload, now, run_id))
            else:
                with conn.cursor() as cur:
                    cur.execute(sql, (status, payload, now, run_id))
                conn.commit()
