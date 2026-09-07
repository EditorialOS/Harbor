"""Authenticated remote MCP adapter for Harbor's canonical product operations."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import Context
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

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
    server = MCPServer(
        "Harbor",
        instructions=(
            "Use Harbor to inspect and run workers for the authenticated workspace. "
            "Tenant identity always comes from the bearer credential."
        ),
        auth=auth_settings,
        token_verifier=token_verifier,
    )

    read_security = [
        {"type": "oauth2", "scopes": ["openid", "email", READ_SCOPE]},
    ]
    run_security = [
        {"type": "oauth2", "scopes": ["openid", "email", READ_SCOPE, RUN_SCOPE]},
    ]

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
        return {
            "tenant_id": tenant.tenant_id,
            "name": tenant.name,
            "timezone": tenant.timezone,
            "sprite_provisioned": bool(tenant.sprite_name),
            "enabled_workers": tenant.config.get("workers", []),
            "outputs": tenant.config.get("outputs", ["files"]),
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
