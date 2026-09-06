"""Harbor production control plane.

Deploy this service on a Fly Machine. It owns tenancy/auth/scheduling and
provisions/dispatches isolated tenant Sprites. It never receives worker secrets
at run time; provider credentials live in Fly Sprites Connectors.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
from typing import Any
from urllib.parse import urlsplit

try:
    from fastapi import Depends, FastAPI, Header, HTTPException
    from pydantic import BaseModel, Field
except ImportError as e:  # pragma: no cover
    raise RuntimeError(
        "Install Harbor's production dependencies to run the control plane"
    ) from e

from .sprite_runner import SpriteRunner
from .tenant_store import (
    TenantStore,
    TenantStoreError,
    validate_non_secret_metadata,
)

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
        raise HTTPException(
            status_code=503, detail="HARBOR_ADMIN_TOKEN is not configured"
        )
    candidate = (authorization or "").removeprefix("Bearer ")
    if not secrets.compare_digest(candidate, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


def _tenant_auth(tenant_id: str, authorization: str | None) -> None:
    candidate = (authorization or "").removeprefix("Bearer ")
    if not candidate or not store.verify_api_key(tenant_id, candidate):
        raise HTTPException(status_code=401, detail="unauthorized")


class TenantCreate(BaseModel):
    tenant_id: str = Field(
        min_length=2, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]+$"
    )
    name: str
    timezone: str = "UTC"
    workers: list[str] = Field(default_factory=lambda: ["newsletter-intelligence"])
    schedule: dict[str, Any] = Field(
        default_factory=lambda: {"newsletter-intelligence": {"hour": 6, "minute": 0}}
    )
    outputs: list[str] = Field(default_factory=lambda: ["files"])


class ConnectionAttach(BaseModel):
    provider: str = Field(
        min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9._-]*$"
    )
    id: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9_-]+$")
    gateway_base_url: str
    settings: dict[str, Any] = Field(default_factory=dict)


class RunRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)


@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "harbor-control-plane"}


@app.post("/v1/tenants", dependencies=[Depends(_admin)])
def create_tenant(req: TenantCreate):
    config = {
        "workers": req.workers,
        "schedule": req.schedule,
        "outputs": req.outputs,
        "connections": [],
    }
    try:
        record, api_key = store.create_tenant(
            req.tenant_id, req.name, req.timezone, config
        )
    except TenantStoreError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {
        "tenant_id": record.tenant_id,
        "api_key": api_key,
        "next": "provision-sprite",
    }


@app.post("/v1/tenants/{tenant_id}/provision-sprite", dependencies=[Depends(_admin)])
def provision_sprite(tenant_id: str):
    try:
        record = store.get(tenant_id)
        sprite_name = record.sprite_name or _sprite_name(tenant_id)
        info = SpriteRunner().provision(sprite_name)
        store.set_sprite(tenant_id, sprite_name, actor_type="admin_api")
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/v1/tenants/{tenant_id}/connections", dependencies=[Depends(_admin)])
def attach_connection(tenant_id: str, req: ConnectionAttach):
    """Attach non-secret connector metadata after the Fly Connector is created.

    The provider credential itself is never accepted by this endpoint.
    """
    parsed_gateway = urlsplit(req.gateway_base_url)
    if parsed_gateway.scheme != "https" or not parsed_gateway.netloc:
        raise HTTPException(
            status_code=422, detail="gateway_base_url must be an absolute HTTPS URL"
        )
    if parsed_gateway.username or parsed_gateway.password:
        raise HTTPException(
            status_code=422, detail="gateway_base_url must not contain credentials"
        )
    expected_path = re.compile(
        rf"^/v1/gateway/[a-z0-9_-]+/{re.escape(req.id)}/?$"
    )
    if (
        parsed_gateway.hostname != "api.sprites.dev"
        or parsed_gateway.query
        or parsed_gateway.fragment
        or not expected_path.fullmatch(parsed_gateway.path)
    ):
        raise HTTPException(
            status_code=422,
            detail="gateway_base_url must identify this connection on the Sprites gateway",
        )
    connection = {
        "id": req.id,
        "provider": req.provider,
        "status": "pending",
        "settings": {
            **req.settings,
            "gateway_base_url": req.gateway_base_url,
            "auth_mode": "sprite_connector",
        },
    }
    try:
        record = store.upsert_connection(
            tenant_id, connection, actor_type="admin_api"
        )
        if not record.sprite_name:
            raise TenantStoreError("tenant Sprite is not provisioned")
        connection_spec = {
            "tenant_id": record.tenant_id,
            "name": record.name,
            "timezone": record.timezone,
            "workspace": "/workspace",
            "workers": record.config.get("workers", []),
            "outputs": record.config.get("outputs", ["files"]),
            "connections": record.config.get("connections", []),
            "provider": req.provider,
        }
        result = SpriteRunner().verify_connection(record.sprite_name, connection_spec)
        store.record_connection_verification(
            tenant_id, req.id, result, actor_type="admin_api"
        )
    except TenantStoreError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        result = {
            "status": "failed",
            "error": {"kind": "probe_failed", "detail": str(e)},
        }
        store.record_connection_verification(
            tenant_id, req.id, result, actor_type="admin_api"
        )
        raise HTTPException(status_code=502, detail=result["error"]) from e
    if result.get("status") != "verified":
        raise HTTPException(status_code=502, detail=result.get("error"))
    return {
        "tenant_id": tenant_id,
        "connection": req.id,
        "provider": req.provider,
        "status": "verified",
        "publication": {
            "id": result.get("publication_id"),
            "name": result.get("publication_name"),
        },
    }


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
        "connections": [
            {
                "id": c.get("id"),
                "provider": c.get("provider"),
                "status": c.get("status"),
                "last_verified_at": c.get("last_verified_at"),
            }
            for c in record.config.get("connections", [])
        ],
    }


@app.post("/v1/tenants/{tenant_id}/workers/{worker_id}/run")
def run_worker_remote(
    tenant_id: str,
    worker_id: str,
    req: RunRequest,
    authorization: str | None = Header(default=None),
):
    _tenant_auth(tenant_id, authorization)
    try:
        validate_non_secret_metadata(req.input, "run.input")
    except TenantStoreError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if str(req.input.get("mode", "")).lower() == "mock":
        raise HTTPException(
            status_code=400,
            detail="mock mode is available only to local developer/test callers",
        )
    if any(str(key).startswith("_harbor_") for key in req.input):
        raise HTTPException(
            status_code=400,
            detail="run input contains a reserved Harbor field",
        )
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
        "run_id": run_id,
        "idempotency_key_hash": hashlib.sha256(idem.encode()).hexdigest(),
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
    except Exception as e:
        store.finish_run(run_id, "failed", {"error": str(e)})
        raise HTTPException(status_code=502, detail=str(e)) from e
    result_status = result.get("status", "failed")
    store.finish_run(run_id, result_status, result)
    if result_status != "completed":
        raise HTTPException(
            status_code=502,
            detail={"run_id": run_id, "worker_status": result_status},
        )
    return {"run_id": run_id, "result": result}
