"""Authenticated remote MCP adapter for Harbor's canonical product operations."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from mcp.server import MCPServer
from mcp.server.apps import Apps, ResourceCsp
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import Context
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from .billing import billing_is_active
from .chatgpt_ui import HARBOR_APP_HTML, HARBOR_APP_URI
from .dispatch import DuplicateRun, RunExecutionFailed, dispatch_worker
from .oauth import READ_SCOPE, RUN_SCOPE, Auth0TokenVerifier, OAuthConfig
from .outputs import DeliveryCoordinator
from .sprite_runner import SpriteRunner
from .tenant_store import RunRecord, TenantRecord, TenantStore, TenantStoreError
from .worker import catalog as worker_catalog
from .workers import alex as _alex  # noqa: F401
from .workers import newsletter_intelligence as _newsletter  # noqa: F401


def _bearer(headers: Any) -> str:
    authorization = headers.get("authorization", "") if headers else ""
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token:
        return ""
    return token


def _tenant_for_context(ctx: Context, store: TenantStore) -> TenantRecord:
    access_token = get_access_token()
    if access_token is not None and access_token.claims:
        tenant_id = access_token.claims.get("tenant_id")
        if isinstance(tenant_id, str) and tenant_id:
            tenant = store.get(tenant_id)
            if tenant.active:
                return tenant
    tenant = store.resolve_api_key(_bearer(ctx.headers))
    if tenant is None:
        raise PermissionError("unauthorized")
    return tenant


def _public_run(record: RunRecord) -> dict[str, Any]:
    result = record.result or {}
    return {
        "run_id": record.run_id,
        "worker_id": record.worker_id,
        "status": record.status,
        "summary": result.get("summary"),
        "attempt_count": record.attempt_count,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
        "deliveries": result.get("deliveries", []),
        "error": record.last_error if record.status == "failed" else None,
    }


def _safe_post(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        key: value.get(key)
        for key in (
            "id",
            "title",
            "published",
            "recipients",
            "delivered",
            "open_rate",
            "click_rate",
            "unsubscribes",
            "spam_reports",
            "web_views",
        )
    }


def _safe_intelligence(result: dict[str, Any]) -> dict[str, Any] | None:
    data = result.get("data") or {}
    intelligence = data.get("intelligence") or data.get("derived")
    metrics = data.get("metrics") or {}
    if not isinstance(intelligence, dict) or not isinstance(metrics, dict):
        return None
    recent_posts = metrics.get("recent_posts") or []
    latest_post = _safe_post(
        intelligence.get("latest") or (recent_posts[0] if recent_posts else None)
    )
    safe_intelligence = {
        key: intelligence.get(key) or []
        for key in (
            "what_changed",
            "why_it_matters",
            "trends",
            "audience_signals",
            "recommendations",
            "anomalies",
        )
    }
    safe_intelligence["headline"] = intelligence.get("headline") or result.get(
        "summary"
    )
    safe_intelligence["strongest_open"] = _safe_post(intelligence.get("best_open"))
    safe_intelligence["weakest_open"] = _safe_post(intelligence.get("weakest_open"))
    safe_intelligence["strongest_click"] = _safe_post(intelligence.get("best_click"))
    safe_intelligence["weakest_click"] = _safe_post(intelligence.get("weakest_click"))
    return {
        "metrics": {
            "publication_name": metrics.get("publication_name"),
            "active_subscribers": metrics.get("active_subscribers"),
            "active_free_subscribers": metrics.get("active_free_subscribers"),
            "active_premium_subscribers": metrics.get("active_premium_subscribers"),
            "avg_open_rate": metrics.get("avg_open_rate"),
            "avg_click_rate": metrics.get("avg_click_rate"),
            "latest_post": latest_post,
        },
        "intelligence": safe_intelligence,
    }


def _dashboard_payload(store: TenantStore, tenant: TenantRecord) -> dict[str, Any]:
    runs = store.list_runs(tenant.tenant_id, limit=10)
    latest = None
    for record in runs:
        if (
            record.worker_id != "newsletter-intelligence"
            or record.status != "completed"
        ):
            continue
        safe = _safe_intelligence(record.result or {})
        if safe is not None:
            latest = {
                "run_id": record.run_id,
                "summary": (record.result or {}).get("summary"),
                "finished_at": record.finished_at,
                **safe,
            }
            break
    enabled = set(tenant.config.get("workers", []))
    sources = [
        {
            "provider": item.get("provider"),
            "label": str(item.get("provider") or "Source").capitalize(),
            "status": item.get("status") or "not_connected",
            "last_verified_at": item.get("last_verified_at"),
        }
        for item in tenant.config.get("connections", [])
    ]
    beehiiv_ready = any(
        source["provider"] == "beehiiv" and source["status"] == "verified"
        for source in sources
    )
    return {
        "workspace": {
            "name": tenant.name,
            "timezone": tenant.timezone,
            "sprite_provisioned": bool(tenant.sprite_name),
        },
        "connection_status": (
            "ready" if tenant.sprite_name and beehiiv_ready else "needs_attention"
        ),
        "sources": sources,
        "workers": [
            {
                **details,
                "enabled": worker_id in enabled,
                "runnable": worker_id != "alex",
            }
            for worker_id, details in worker_catalog().items()
        ],
        "recent_runs": [_public_run(record) for record in runs],
        "latest_intelligence": latest,
    }


class TenantBearerMiddleware:
    """Reject unauthenticated HTTP requests before MCP parses their content."""

    def __init__(self, app: Any, store: TenantStore):
        self.app = app
        self.store = store

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        if self.store.resolve_api_key(_bearer(headers)) is None:
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"www-authenticate", b'Bearer realm="harbor-mcp"'),
                    ],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b'{"error":"unauthorized"}',
                }
            )
            return
        await self.app(scope, receive, send)


@dataclass(frozen=True)
class RemoteMCP:
    server: MCPServer
    app: Any
    oauth_config: OAuthConfig | None = None


def _transport_security() -> TransportSecuritySettings:
    public_url = os.environ.get("HARBOR_PUBLIC_URL")
    if not public_url and os.environ.get("FLY_APP_NAME"):
        public_url = f"https://{os.environ['FLY_APP_NAME']}.fly.dev"
    parsed = urlsplit(public_url or "http://localhost:8080")
    hostname = parsed.hostname or "localhost"
    hosts = [hostname, f"{hostname}:*"]
    origins = [f"{parsed.scheme}://{parsed.netloc}"] if parsed.netloc else []
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )


def create_remote_mcp(
    store: TenantStore,
    runner_factory: Any = SpriteRunner,
    *,
    oauth_config: OAuthConfig | None = None,
    token_verifier: TokenVerifier | None = None,
) -> RemoteMCP:
    oauth_config = oauth_config if oauth_config is not None else OAuthConfig.from_env()
    auth_settings = None
    if oauth_config is not None:
        auth_settings = AuthSettings(
            issuer_url=oauth_config.issuer,
            resource_server_url=oauth_config.resource,
            required_scopes=list(oauth_config.required_scopes),
            validate_token_resource=True,
        )
        token_verifier = token_verifier or Auth0TokenVerifier(store, oauth_config)
    read_security = [
        {"type": "oauth2", "scopes": ["openid", "email", READ_SCOPE]},
    ]
    run_security = [
        {"type": "oauth2", "scopes": ["openid", "email", READ_SCOPE, RUN_SCOPE]},
    ]
    apps = Apps()
    apps.add_html_resource(
        HARBOR_APP_URI,
        HARBOR_APP_HTML,
        name="Harbor dashboard",
        title="Harbor",
        description="Editorial dashboard for a Harbor workspace.",
        csp=ResourceCsp(connect_domains=[], resource_domains=[]),
        prefers_border=True,
    )

    @apps.tool(
        resource_uri=HARBOR_APP_URI,
        visibility=["model", "app"],
        name="harbor_dashboard",
        title="Show Harbor dashboard",
        description=(
            "Render the authenticated workspace’s latest intelligence, sources, "
            "workers, recommendations, runs, and connection status."
        ),
        annotations=ToolAnnotations(readOnlyHint=True),
        meta={
            "securitySchemes": read_security,
            "openai/toolInvocation/invoking": "Opening Harbor…",
            "openai/toolInvocation/invoked": "Harbor is ready.",
        },
    )
    def dashboard(ctx: Context) -> dict[str, Any]:
        tenant = _tenant_for_context(ctx, store)
        return _dashboard_payload(store, tenant)

    server = MCPServer(
        "Harbor",
        title="Harbor",
        description="Run and inspect tenant-isolated AI workers.",
        instructions=(
            "Use Harbor to inspect and run workers for the authenticated workspace. "
            "Use harbor_dashboard when the user asks to see or open Harbor. "
            "Tenant identity always comes from the bearer credential."
        ),
        auth=auth_settings,
        token_verifier=token_verifier,
        extensions=[apps],
    )

    @server.tool(
        name="harbor_worker_catalog",
        annotations=ToolAnnotations(readOnlyHint=True),
        meta={"securitySchemes": read_security},
    )
    def catalog(ctx: Context) -> dict[str, Any]:
        """List Harbor workers and whether they are enabled and runnable."""
        tenant = _tenant_for_context(ctx, store)
        enabled = set(tenant.config.get("workers", []))
        return {
            "workers": [
                {
                    **details,
                    "enabled": worker_id in enabled,
                    "runnable": worker_id != "alex",
                }
                for worker_id, details in worker_catalog().items()
            ]
        }

    @server.tool(
        name="harbor_status",
        annotations=ToolAnnotations(readOnlyHint=True),
        meta={"securitySchemes": read_security},
    )
    def status(ctx: Context) -> dict[str, Any]:
        """Get safe status for the authenticated Harbor workspace."""
        tenant = _tenant_for_context(ctx, store)
        billing = store.get_billing(tenant.tenant_id)
        return {
            "tenant_id": tenant.tenant_id,
            "name": tenant.name,
            "timezone": tenant.timezone,
            "sprite_provisioned": bool(tenant.sprite_name),
            "enabled_workers": tenant.config.get("workers", []),
            "outputs": tenant.config.get("outputs", ["files"]),
            "billing": {
                "required": bool(tenant.config.get("billing_required")),
                "plan": billing.plan if billing else None,
                "status": billing.status if billing else "not_configured",
            },
            "connections": [
                {
                    "provider": item.get("provider"),
                    "status": item.get("status"),
                    "last_verified_at": item.get("last_verified_at"),
                }
                for item in tenant.config.get("connections", [])
            ],
        }

    @server.tool(
        name="harbor_enabled_workers",
        annotations=ToolAnnotations(readOnlyHint=True),
        meta={"securitySchemes": read_security},
    )
    def enabled_workers(ctx: Context) -> dict[str, Any]:
        """List workers enabled for the authenticated workspace."""
        tenant = _tenant_for_context(ctx, store)
        return {"workers": tenant.config.get("workers", [])}

    @server.tool(
        name="harbor_recent_runs",
        annotations=ToolAnnotations(readOnlyHint=True),
        meta={"securitySchemes": read_security},
    )
    def recent_runs(ctx: Context, limit: int = 10) -> dict[str, Any]:
        """List recent run status without exposing tenant filesystem paths."""
        tenant = _tenant_for_context(ctx, store)
        return {
            "runs": [
                _public_run(run) for run in store.list_runs(tenant.tenant_id, limit)
            ]
        }

    @server.tool(
        name="harbor_run_worker",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
        meta={"securitySchemes": run_security},
    )
    def run_worker(
        ctx: Context,
        worker_id: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Run one enabled worker in the authenticated tenant's private Sprite."""
        tenant = _tenant_for_context(ctx, store)
        if tenant.config.get("billing_required") and not billing_is_active(
            store.get_billing(tenant.tenant_id)
        ):
            raise PermissionError("an active Harbor plan is required")
        if idempotency_key is not None and not 1 <= len(idempotency_key) <= 255:
            raise ValueError("idempotency_key must contain 1 through 255 characters")
        if worker_id not in tenant.config.get("workers", []):
            raise PermissionError("worker is not enabled")
        runner = runner_factory()
        idem = idempotency_key or ("mcp_" + secrets.token_urlsafe(24))
        try:
            run_id, result = dispatch_worker(
                store,
                runner,
                tenant,
                worker_id,
                {},
                idem,
                delivery_handler=DeliveryCoordinator(store, runner).deliver,
            )
        except DuplicateRun as error:
            if error.record is None:
                raise TenantStoreError("duplicate run record was not found") from error
            return {"duplicate_suppressed": True, **_public_run(error.record)}
        except RunExecutionFailed as error:
            return {
                "run_id": error.run_id,
                "status": "failed",
                "attempt_count": error.result.get("attempts"),
            }
        record = store.get_run_by_idempotency(
            tenant.tenant_id,
            worker_id,
            idem,
        )
        if record is not None:
            return _public_run(record)
        return {
            "run_id": run_id,
            "status": result.get("status"),
            "summary": result.get("summary"),
            "attempt_count": result.get("attempts"),
            "deliveries": result.get("deliveries", []),
        }

    asgi = server.streamable_http_app(
        streamable_http_path="/",
        json_response=True,
        stateless_http=True,
        max_request_body_size=1024 * 1024,
        transport_security=_transport_security(),
        host="0.0.0.0",
    )
    if oauth_config is not None:
        return RemoteMCP(server, asgi, oauth_config)
    return RemoteMCP(server, TenantBearerMiddleware(asgi, store), None)
