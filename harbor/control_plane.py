"""Harbor production control plane.

Deploy this service on a Fly Machine. It owns tenancy/auth/scheduling and
provisions/dispatches isolated tenant Sprites. It never receives worker secrets
at run time; provider credentials live in Fly Sprites Connectors.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import secrets
from typing import Any

try:
    from fastapi import Depends, FastAPI, Header, HTTPException
    from pydantic import BaseModel, Field
except ImportError as e:  # pragma: no cover
    raise RuntimeError("Install Harbor's production dependencies to run the control plane") from e

from .sprite_runner import SpriteRunner
from .tenant_store import TenantStore, TenantStoreError

app = FastAPI(title="Harbor Control Plane", version="0.9.0-alpha")
store = TenantStore()


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    return value[:32] or "tenant"


def _sprite_name(tenant_id: str) -> str:
    suffix = hashlib.sha256(tenant_id.encode()).hexdigest()[:8]
    return f"harbor-{_slug(tenant_id)}-{suffix}"[:63]


def _admin(authorization: str | None = Header(default=None)) -> None:
    expected = os.environ.get("HARBOR_ADMIN_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="HARBOR_ADMIN_TOKEN is not configured")
    candidate = (authorization or "").removeprefix("Bearer ")
    if not secrets.compare_digest(candidate, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


def _tenant_auth(tenant_id: str, authorization: str | None) -> None:
    candidate = (authorization or "").removeprefix("Bearer ")
    if not candidate or not store.verify_api_key(tenant_id, candidate):
        raise HTTPException(status_code=401, detail="unauthorized")


class TenantCreate(BaseModel):
    tenant_id: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]+$")
    name: str
    timezone: str = "UTC"
    workers: list[str] = ["newsletter-intelligence"]
    schedule: dict[str, Any] = {"newsletter-intelligence": {"hour": 6, "minute": 0}}
    outputs: list[str] = ["files"]


class ConnectionAttach(BaseModel):
    provider: str
    id: str
    gateway_base_url: str
    settings: dict[str, Any] = {}


class RunRequest(BaseModel):
    input: dict[str, Any] = {}
    idempotency_key: str | None = None


@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "harbor-control-plane"}


@app.post("/v1/tenants", dependencies=[Depends(_admin)])
def create_tenant(req: TenantCreate):
    config = {"workers": req.workers, "schedule": req.schedule, "outputs": req.outputs, "connections": []}
    try:
        record, api_key = store.create_tenant(req.tenant_id, req.name, req.timezone, config)
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {"tenant_id": record.tenant_id, "api_key": api_key, "next": "provision-sprite"}


@app.post("/v1/tenants/{tenant_id}/provision-sprite", dependencies=[Depends(_admin)])
def provision_sprite(tenant_id: str):
    try:
        record = store.get(tenant_id)
        sprite_name = record.sprite_name or _sprite_name(tenant_id)
        info = SpriteRunner().provision(sprite_name)
        store.set_sprite(tenant_id, sprite_name)
        return info
    except (TenantStoreError, Exception) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/v1/tenants/{tenant_id}/connections", dependencies=[Depends(_admin)])
def attach_connection(tenant_id: str, req: ConnectionAttach):
    """Attach non-secret connector metadata after the Fly Connector is created.

    The provider credential itself is never accepted by this endpoint.
    """
    record = store.get(tenant_id)
    config = dict(record.config)
    conns = [c for c in config.get("connections", []) if c.get("id") != req.id]
    conns.append({
        "id": req.id,
        "provider": req.provider,
        "settings": {**req.settings, "gateway_base_url": req.gateway_base_url, "auth_mode": "sprite_connector"},
    })
    config["connections"] = conns
    # Minimal metadata update; use direct SQL through the store connection until
    # the configuration service is split into its own repository layer.
    payload = json.dumps(config)
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    with store._connect() as conn:  # internal, kept in one module for alpha
        if store.kind == "sqlite":
            conn.execute("UPDATE tenants SET config_json=?,updated_at=? WHERE tenant_id=?", (payload, now, tenant_id))
        else:
            with conn.cursor() as cur:
                cur.execute("UPDATE tenants SET config_json=%s::jsonb,updated_at=%s WHERE tenant_id=%s", (payload, now, tenant_id))
            conn.commit()
    return {"tenant_id": tenant_id, "connection": req.id, "provider": req.provider}


@app.get("/v1/tenants/{tenant_id}/status")
def tenant_status(tenant_id: str, authorization: str | None = Header(default=None)):
    _tenant_auth(tenant_id, authorization)
    record = store.get(tenant_id)
    return {
        "tenant_id": record.tenant_id,
        "name": record.name,
        "timezone": record.timezone,
        "sprite_name": record.sprite_name,
        "workers": record.config.get("workers", []),
        "connections": [{"id": c.get("id"), "provider": c.get("provider")} for c in record.config.get("connections", [])],
    }


@app.post("/v1/tenants/{tenant_id}/workers/{worker_id}/run")
def run_worker_remote(tenant_id: str, worker_id: str, req: RunRequest, authorization: str | None = Header(default=None)):
    _tenant_auth(tenant_id, authorization)
    record = store.get(tenant_id)
    if worker_id not in record.config.get("workers", []):
        raise HTTPException(status_code=403, detail="worker not enabled")
    if not record.sprite_name:
        raise HTTPException(status_code=409, detail="tenant Sprite is not provisioned")

    run_id = "run_" + secrets.token_hex(12)
    idem = req.idempotency_key or run_id
    if not store.claim_run(run_id, tenant_id, worker_id, idem):
        raise HTTPException(status_code=409, detail="duplicate idempotency key")

    run_spec = {
        "tenant_id": record.tenant_id,
        "name": record.name,
        "timezone": record.timezone,
        "workspace": "/workspace",
        "workers": record.config.get("workers", []),
        "outputs": record.config.get("outputs", ["files"]),
        "schedule": record.config.get("schedule", {}),
        "connections": record.config.get("connections", []),
        "worker": worker_id,
        "input": req.input,
    }
    try:
        result = SpriteRunner().run(record.sprite_name, run_spec)
        store.finish_run(run_id, result.get("status", "completed"), result)
        return {"run_id": run_id, "result": result}
    except Exception as e:
        store.finish_run(run_id, "failed", {"error": str(e)})
        raise HTTPException(status_code=502, detail=str(e)) from e
