"""Harbor production control plane.

Deploy this service on a Fly Machine. It owns tenancy/auth/scheduling and
provisions/dispatches isolated tenant Sprites. It never receives worker secrets
at run time; provider credentials live in Fly Sprites Connectors.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import os
import re
import secrets
from typing import Any
from urllib.parse import urlsplit

try:
    from fastapi import Depends, FastAPI, Header, HTTPException
    from fastapi.responses import PlainTextResponse
    from pydantic import BaseModel, ConfigDict, Field
except ImportError as e:  # pragma: no cover
    raise RuntimeError(
        "Install Harbor's production dependencies to run the control plane"
    ) from e

from .billing import billing_is_active
from .dispatch import DuplicateRun, RunExecutionFailed, dispatch_worker
from .outputs import DeliveryCoordinator, DeliveryError, validate_email_recipient
from .remote_mcp import create_remote_mcp
from .scheduler import (
    DailySchedule,
    next_occurrence,
    next_report_occurrence,
    parse_daily_schedule,
    parse_report_schedule,
)
from .sprite_runner import SpriteRunner
from .tenant_store import (
    LATEST_SCHEMA_VERSION,
    TenantStore,
    TenantStoreError,
    validate_non_secret_metadata,
)
from .time_ranges import resolve_date_window
from .web_portal import create_web_router

store = TenantStore()
remote_mcp = create_remote_mcp(store)


@contextlib.asynccontextmanager
async def _lifespan(_app: FastAPI):
    async with remote_mcp.server.session_manager.run():
        yield


app = FastAPI(title="Harbor Control Plane", version="1.0.0-rc.5", lifespan=_lifespan)
app.mount("/mcp", remote_mcp.app)


@app.middleware("http")
async def production_security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    return response


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


class ScheduleUpdate(BaseModel):
    hour: int = Field(ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    timezone: str | None = Field(default=None, min_length=1, max_length=128)


class ReportScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    schedule: dict[str, Any]
    timeframe: str
    view: str = Field(default="portfolio", pattern=r"^(publication|portfolio)$")
    provider: str | None = Field(
        default=None, pattern=r"^[a-z0-9][a-z0-9._-]*$"
    )
    connection_ids: list[str] = Field(default_factory=list, max_length=50)
    publication_ids: list[str] = Field(default_factory=list, max_length=50)
    start_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    issue_limit: int = Field(default=100, ge=1, le=1000)
    email_recipients: list[str] = Field(default_factory=list, max_length=50)
    email_subject: str = Field(default="Harbor Intelligence", max_length=100)


class EmailOutputUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    recipients: list[str] = Field(default_factory=list, max_length=50)
    subject_prefix: str = Field(default="Harbor Morning Intelligence", max_length=100)


class OnboardingInvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    expires_in_hours: int = Field(default=24, ge=1, le=168)


class WorkspaceOwnerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)


@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "harbor-control-plane"}


@app.get("/.well-known/oauth-protected-resource", include_in_schema=False)
@app.get("/.well-known/oauth-protected-resource/mcp", include_in_schema=False)
def oauth_protected_resource_metadata():
    if remote_mcp.oauth_config is None:
        raise HTTPException(status_code=404, detail="OAuth is not configured")
    return remote_mcp.oauth_config.protected_resource_metadata()


@app.get(
    "/.well-known/openai-apps-challenge",
    response_class=PlainTextResponse,
    include_in_schema=False,
)
def openai_apps_challenge():
    """Serve the exact per-submission token issued by OpenAI's review portal."""
    token = os.environ.get("HARBOR_OPENAI_APPS_CHALLENGE", "")
    if not token:
        raise HTTPException(status_code=404, detail="challenge is not configured")
    if len(token) > 512 or "\r" in token or "\n" in token:
        raise HTTPException(status_code=503, detail="challenge is misconfigured")
    return PlainTextResponse(token)


@app.get("/readyz")
def readyz():
    try:
        version = store.schema_version
    except Exception as error:
        raise HTTPException(status_code=503, detail="database unavailable") from error
    if version != LATEST_SCHEMA_VERSION:
        raise HTTPException(status_code=503, detail="database schema is not current")
    return {
        "ok": True,
        "service": "harbor-control-plane",
        "database_schema_version": version,
    }


def _prometheus_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


@app.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
def metrics():
    try:
        snapshot = store.operational_snapshot()
    except Exception:  # noqa: BLE001 - health boundary must survive driver failures
        return PlainTextResponse(
            "# TYPE harbor_metrics_up gauge\nharbor_metrics_up 0\n",
            status_code=503,
        )
    lines = [
        "# TYPE harbor_metrics_up gauge",
        "harbor_metrics_up 1",
        "# TYPE harbor_database_schema_version gauge",
        f"harbor_database_schema_version {snapshot['schema_version']}",
        "# TYPE harbor_tenants_active gauge",
        f"harbor_tenants_active {snapshot['active_tenants']}",
        "# TYPE harbor_runs gauge",
    ]
    for status, count in sorted(snapshot["runs"].items()):
        lines.append(f'harbor_runs{{status="{_prometheus_label(status)}"}} {count}')
    lines.append("# TYPE harbor_deliveries gauge")
    for status, count in sorted(snapshot["deliveries"].items()):
        lines.append(
            f'harbor_deliveries{{status="{_prometheus_label(status)}"}} {count}'
        )
    heartbeat_status = _prometheus_label(snapshot["scheduler_heartbeat_status"])
    lines.extend(
        [
            "# TYPE harbor_schedule_overdue gauge",
            f"harbor_schedule_overdue {snapshot['overdue_schedules']}",
            "# TYPE harbor_run_leases_expired gauge",
            f"harbor_run_leases_expired {snapshot['expired_run_leases']}",
            "# TYPE harbor_scheduler_heartbeat gauge",
            f'harbor_scheduler_heartbeat{{status="{heartbeat_status}"}} 1',
            "# TYPE harbor_scheduler_heartbeat_age_seconds gauge",
        ]
    )
    heartbeat_age = snapshot["scheduler_heartbeat_age_seconds"]
    lines.append(
        "harbor_scheduler_heartbeat_age_seconds "
        + (str(heartbeat_age) if heartbeat_age is not None else "-1")
    )
    return "\n".join(lines) + "\n"


@app.post("/v1/tenants", dependencies=[Depends(_admin)])
def create_tenant(req: TenantCreate):
    try:
        for worker_id, raw_schedule in req.schedule.items():
            if worker_id not in req.workers:
                raise ValueError(
                    f"scheduled worker '{worker_id}' is not enabled for this tenant"
                )
            next_occurrence(
                dt.datetime.now(dt.timezone.utc),
                req.timezone,
                parse_daily_schedule(raw_schedule),
            )
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
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


@app.put("/v1/tenants/{tenant_id}/owner", dependencies=[Depends(_admin)])
def update_workspace_owner(tenant_id: str, req: WorkspaceOwnerUpdate):
    try:
        email = validate_email_recipient(req.email)
        store.set_workspace_owner(tenant_id, email)
    except (DeliveryError, TenantStoreError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"tenant_id": tenant_id, "owner_configured": True}


@app.post("/v1/onboarding/invitations", dependencies=[Depends(_admin)])
def create_onboarding_invitation(req: OnboardingInvitationCreate):
    """Issue a one-time code; only its hash is persisted."""
    try:
        email = validate_email_recipient(req.email)
        invitation, code = store.create_onboarding_invitation(
            email, expires_in_hours=req.expires_in_hours
        )
    except (DeliveryError, TenantStoreError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {
        "invitation_id": invitation.invitation_id,
        "invitation_code": code,
        "email": invitation.email,
        "expires_at": invitation.expires_at,
        "onboarding_path": "/onboarding",
    }


@app.post("/v1/tenants/{tenant_id}/provision-sprite", dependencies=[Depends(_admin)])
def provision_sprite(tenant_id: str):
    try:
        record = store.get(tenant_id)
        sprite_name = record.sprite_name or _sprite_name(tenant_id)
        store.record_provisioning_status(
            tenant_id, "provisioning", actor_type="admin_api"
        )
        info = SpriteRunner().provision(sprite_name)
        store.set_sprite(tenant_id, sprite_name, actor_type="admin_api")
        store.record_provisioning_status(tenant_id, "ready", actor_type="admin_api")
        return info
    except Exception as e:
        with contextlib.suppress(TenantStoreError):
            store.record_provisioning_status(
                tenant_id,
                "failed",
                error_type=type(e).__name__,
                actor_type="admin_api",
            )
        raise HTTPException(status_code=500, detail="Sprite provisioning failed") from e


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
    expected_path = re.compile(rf"^/v1/gateway/[a-z0-9_-]+/{re.escape(req.id)}/?$")
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
        record = store.upsert_connection(tenant_id, connection, actor_type="admin_api")
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
    billing = store.get_billing(tenant_id)
    schedule_state = {
        worker_id: store.get_schedule_state(tenant_id, worker_id)
        for worker_id in record.config.get("schedule", {})
    }
    report_schedule_state = {
        str(item.get("id")): store.get_schedule_state(
            tenant_id, f"report:{item.get('id')}"
        )
        for item in record.config.get("report_schedules", [])
        if item.get("id")
    }
    return {
        "tenant_id": record.tenant_id,
        "name": record.name,
        "timezone": record.timezone,
        "sprite_name": record.sprite_name,
        "provisioning": record.config.get("provisioning")
        or {"status": "ready" if record.sprite_name else "pending"},
        "workers": record.config.get("workers", []),
        "schedule": record.config.get("schedule", {}),
        "schedule_state": {
            worker_id: {
                "next_run_at": state.next_run_at,
                "last_run_id": state.last_run_id,
                "last_status": state.last_status,
                "attempt_count": state.attempt_count,
            }
            for worker_id, state in schedule_state.items()
            if state is not None
        },
        "report_schedules": [
            {
                "id": item.get("id"),
                "label": item.get("label"),
                "enabled": item.get("enabled", True),
                "schedule": item.get("schedule"),
                "timeframe": (item.get("input") or {}).get("timeframe"),
                "view": (item.get("input") or {}).get("view"),
                "source_count": len((item.get("input") or {}).get("connection_ids", [])),
                "publication_count": len(
                    (item.get("input") or {}).get("publication_ids", [])
                ),
                "recipient_count": len(
                    ((item.get("output_settings") or {}).get("email") or {}).get(
                        "recipients", []
                    )
                ),
                "next_run_at": (
                    report_schedule_state[str(item.get("id"))].next_run_at
                    if report_schedule_state.get(str(item.get("id"))) is not None
                    else None
                ),
                "last_status": (
                    report_schedule_state[str(item.get("id"))].last_status
                    if report_schedule_state.get(str(item.get("id"))) is not None
                    else "not_scheduled"
                ),
            }
            for item in record.config.get("report_schedules", [])
        ],
        "outputs": record.config.get("outputs", ["files"]),
        "email_output": {
            "configured": bool(
                (record.config.get("output_settings") or {}).get("email")
            ),
            "recipient_count": len(
                ((record.config.get("output_settings") or {}).get("email") or {}).get(
                    "recipients", []
                )
            ),
        },
        "connections": [
            {
                "id": c.get("id"),
                "provider": c.get("provider"),
                "status": c.get("status"),
                "last_verified_at": c.get("last_verified_at"),
            }
            for c in record.config.get("connections", [])
        ],
        "billing": {
            "required": bool(record.config.get("billing_required")),
            "plan": billing.plan if billing else None,
            "status": billing.status if billing else "not_configured",
        },
    }


@app.put("/v1/tenants/{tenant_id}/workers/{worker_id}/schedule")
def update_worker_schedule(
    tenant_id: str,
    worker_id: str,
    req: ScheduleUpdate,
    authorization: str | None = Header(default=None),
):
    _tenant_auth(tenant_id, authorization)
    record = store.get(tenant_id)
    timezone = req.timezone or record.timezone
    schedule = DailySchedule(req.hour, req.minute)
    try:
        next_at = next_occurrence(dt.datetime.now(dt.timezone.utc), timezone, schedule)
        store.update_worker_schedule(
            tenant_id,
            worker_id,
            {"hour": req.hour, "minute": req.minute},
            timezone,
            next_at.isoformat(),
        )
    except (TenantStoreError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {
        "tenant_id": tenant_id,
        "worker_id": worker_id,
        "timezone": timezone,
        "schedule": {"hour": req.hour, "minute": req.minute},
        "next_run_at": next_at.isoformat(),
    }


@app.put("/v1/tenants/{tenant_id}/report-schedules/{schedule_id}")
def update_report_schedule(
    tenant_id: str,
    schedule_id: str,
    req: ReportScheduleUpdate,
    authorization: str | None = Header(default=None),
):
    """Create or replace one independently scheduled Newsletter Intelligence report."""
    _tenant_auth(tenant_id, authorization)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", schedule_id):
        raise HTTPException(status_code=422, detail="report schedule id is invalid")
    try:
        record = store.get(tenant_id)
        schedule = parse_report_schedule(req.schedule)
        window = resolve_date_window(
            req.timeframe,
            timezone=record.timezone,
            start_date=req.start_date,
            end_date=req.end_date,
        )
        recipients = [
            validate_email_recipient(item) for item in req.email_recipients
        ]
        if "\r" in req.email_subject or "\n" in req.email_subject:
            raise DeliveryError("email subject is invalid")
        if req.view == "publication" and len(req.publication_ids) != 1:
            raise ValueError(
                "publication reports require exactly one selected publication"
            )
        report = {
            "id": schedule_id,
            "label": req.label,
            "enabled": req.enabled,
            "worker_id": "newsletter-intelligence",
            "schedule": req.schedule,
            "input": {
                "timeframe": window.label,
                "view": req.view,
                "recent_posts": req.issue_limit,
                **({"provider": req.provider} if req.provider else {}),
                **(
                    {"connection_ids": req.connection_ids}
                    if req.connection_ids
                    else {}
                ),
                **(
                    {"publication_ids": req.publication_ids}
                    if req.publication_ids
                    else {}
                ),
                **({"start_date": req.start_date} if req.start_date else {}),
                **({"end_date": req.end_date} if req.end_date else {}),
            },
            "output_settings": (
                {
                    "email": {
                        "recipients": recipients,
                        "subject_prefix": req.email_subject,
                    }
                }
                if recipients
                else {}
            ),
        }
        validate_non_secret_metadata(report, "report_schedule")
        config = dict(record.config)
        reports = [
            item
            for item in config.get("report_schedules", [])
            if item.get("id") != schedule_id
        ]
        reports.append(report)
        config["report_schedules"] = reports
        store.update_config(tenant_id, config, actor_type="tenant_api")
        next_at = next_report_occurrence(
            dt.datetime.now(dt.timezone.utc), record.timezone, schedule
        )
        store.upsert_schedule_state(
            tenant_id,
            f"report:{schedule_id}",
            next_run_at=next_at.isoformat(),
            last_status="scheduled" if req.enabled else "disabled",
        )
    except (DeliveryError, TenantStoreError, TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {
        "tenant_id": tenant_id,
        "schedule_id": schedule_id,
        "enabled": req.enabled,
        "timeframe": window.label,
        "next_run_at": next_at.isoformat() if req.enabled else None,
        "recipient_count": len(recipients),
    }


@app.put("/v1/tenants/{tenant_id}/outputs/email")
def update_email_output(
    tenant_id: str,
    req: EmailOutputUpdate,
    authorization: str | None = Header(default=None),
):
    _tenant_auth(tenant_id, authorization)
    if req.enabled and not req.recipients:
        raise HTTPException(
            status_code=422, detail="at least one email recipient is required"
        )
    try:
        recipients = [validate_email_recipient(item) for item in req.recipients]
        if "\r" in req.subject_prefix or "\n" in req.subject_prefix:
            raise DeliveryError("email subject prefix is invalid")
        record = store.configure_email_output(
            tenant_id,
            enabled=req.enabled,
            recipients=recipients,
            subject_prefix=req.subject_prefix,
        )
    except (DeliveryError, TenantStoreError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {
        "tenant_id": tenant_id,
        "enabled": "email" in record.config.get("outputs", []),
        "recipient_count": len(recipients),
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
    if req.input:
        raise HTTPException(
            status_code=400,
            detail="this worker does not accept remote run input fields",
        )
    record = store.get(tenant_id)
    if record.config.get("billing_required") and not billing_is_active(
        store.get_billing(tenant_id)
    ):
        raise HTTPException(status_code=402, detail="an active Harbor plan is required")
    if worker_id not in record.config.get("workers", []):
        raise HTTPException(status_code=403, detail="worker not enabled")
    if not record.sprite_name:
        raise HTTPException(status_code=409, detail="tenant Sprite is not provisioned")

    idem = req.idempotency_key or ("request_" + secrets.token_urlsafe(24))
    try:
        runner = SpriteRunner()
        run_id, result = dispatch_worker(
            store,
            runner,
            record,
            worker_id,
            req.input,
            idem,
            delivery_handler=DeliveryCoordinator(store, runner).deliver,
        )
    except DuplicateRun as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RunExecutionFailed as error:
        raise HTTPException(
            status_code=502,
            detail={"run_id": error.run_id, "worker_status": "failed"},
        ) from error
    except TenantStoreError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"run_id": run_id, "result": result}


app.include_router(create_web_router(lambda: store, lambda: SpriteRunner()))
