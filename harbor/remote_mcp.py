"""Authenticated remote MCP adapter for Harbor's canonical product operations."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Annotated, Any, Literal, NotRequired, TypedDict
from urllib.parse import urlsplit

from mcp.server import MCPServer
from mcp.server.apps import Apps, ResourceCsp
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import Context
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field

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

Timeframe = Literal[
    "today",
    "yesterday",
    "last_7_days",
    "week",
    "month",
    "last_30_days",
    "quarter",
    "last_90_days",
    "six_months",
    "ytd",
    "previous_year",
    "custom",
]
NewsletterView = Literal["publication", "portfolio"]


class PublicDelivery(TypedDict):
    adapter: str | None
    status: str | None
    attempt_count: int | None
    duplicate_suppressed: bool | None


class PublicRun(TypedDict):
    run_id: str
    worker_id: str
    status: str
    summary: str | None
    attempt_count: int
    started_at: str
    finished_at: str | None
    deliveries: list[PublicDelivery]
    error: str | None


class PublicPost(TypedDict):
    title: str | None
    published: str | None
    recipients: int | None
    delivered: int | None
    open_rate: float | None
    click_rate: float | None
    unsubscribes: int | None
    spam_reports: int | None
    web_views: int | None
    publication_id: NotRequired[str | None]
    publication_name: NotRequired[str | None]
    provider: NotRequired[str | None]
    metric_states: NotRequired[dict[str, Any]]


class PublicIntelligence(TypedDict):
    what_changed: list[str]
    why_it_matters: list[str]
    trends: list[dict[str, Any]]
    audience_signals: list[str]
    recommendations: list[str]
    anomalies: list[str]
    headline: str | None
    strongest_open: PublicPost | None
    weakest_open: PublicPost | None
    strongest_click: PublicPost | None
    weakest_click: PublicPost | None
    strongest_publication: NotRequired[dict[str, Any] | None]
    weakest_publication: NotRequired[dict[str, Any] | None]
    window: NotRequired[dict[str, Any] | None]
    comparison_window: NotRequired[dict[str, Any] | None]


class PublicMetrics(TypedDict):
    publication_name: str | None
    active_subscribers: int | None
    active_free_subscribers: int | None
    active_premium_subscribers: int | None
    avg_open_rate: float | None
    avg_click_rate: float | None
    latest_post: PublicPost | None
    publication_count: NotRequired[int | None]
    publications: NotRequired[list[dict[str, Any]]]
    window: NotRequired[dict[str, Any] | None]
    metric_states: NotRequired[dict[str, Any]]


class LatestIntelligence(TypedDict):
    run_id: str
    summary: str | None
    finished_at: str | None
    metrics: PublicMetrics
    intelligence: PublicIntelligence


class PublicWorker(TypedDict):
    id: str
    label: str
    enabled: bool
    runnable: bool


class PublicSource(TypedDict):
    provider: str | None
    label: str
    status: str
    last_verified_at: str | None


class WorkspaceSummary(TypedDict):
    name: str
    timezone: str
    sprite_provisioned: bool


class DashboardOutput(TypedDict):
    workspace: WorkspaceSummary
    connection_status: str
    sources: list[PublicSource]
    workers: list[PublicWorker]
    recent_runs: list[PublicRun]
    latest_intelligence: LatestIntelligence | None


class WorkerCatalogOutput(TypedDict):
    workers: list[PublicWorker]


class BillingSummary(TypedDict):
    required: bool
    plan: str | None
    status: str


class ConnectionSummary(TypedDict):
    provider: str | None
    status: str | None
    last_verified_at: str | None


class StatusOutput(TypedDict):
    name: str
    timezone: str
    sprite_provisioned: bool
    enabled_workers: list[str]
    outputs: list[str]
    billing: BillingSummary
    connections: list[ConnectionSummary]


class EnabledWorkersOutput(TypedDict):
    workers: list[str]


class RecentRunsOutput(TypedDict):
    runs: list[PublicRun]


class RunWorkerOutput(TypedDict):
    run_id: str
    status: str
    duplicate_suppressed: NotRequired[bool]
    worker_id: NotRequired[str]
    summary: NotRequired[str | None]
    attempt_count: NotRequired[int | None]
    started_at: NotRequired[str]
    finished_at: NotRequired[str | None]
    deliveries: NotRequired[list[PublicDelivery]]
    error: NotRequired[str | None]
    latest_intelligence: NotRequired[LatestIntelligence | None]


class IntelligenceQueryOutput(TypedDict):
    found: bool
    latest_intelligence: LatestIntelligence | None


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


def _public_deliveries(value: Any) -> list[PublicDelivery]:
    if not isinstance(value, list):
        return []
    return [
        {
            key: delivery.get(key)
            for key in (
                "adapter",
                "status",
                "attempt_count",
                "duplicate_suppressed",
            )
        }
        for delivery in value
        if isinstance(delivery, dict)
    ]


def _public_run(record: RunRecord) -> PublicRun:
    result = record.result or {}
    return {
        "run_id": record.run_id,
        "worker_id": record.worker_id,
        "status": record.status,
        "summary": result.get("summary"),
        "attempt_count": record.attempt_count,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
        "deliveries": _public_deliveries(result.get("deliveries")),
        "error": record.last_error if record.status == "failed" else None,
    }


def _safe_post(value: Any) -> PublicPost | None:
    if not isinstance(value, dict):
        return None
    result = {
        key: value.get(key)
        for key in (
            "title",
            "published",
            "recipients",
            "delivered",
            "open_rate",
            "click_rate",
            "unsubscribes",
            "spam_reports",
            "web_views",
            "publication_id",
            "publication_name",
            "provider",
        )
    }
    states = value.get("metric_states")
    if isinstance(states, dict):
        result["metric_states"] = states
    return result


def _safe_intelligence(result: dict[str, Any]) -> dict[str, Any] | None:
    data = result.get("data") or {}
    intelligence = data.get("intelligence") or data.get("derived")
    metrics = data.get("metrics") or {}
    if not isinstance(intelligence, dict) or not isinstance(metrics, dict):
        return None
    recent_posts = metrics.get("recent_posts") or []
    normalized_publications = (
        (data.get("newsletter_data") or {}).get("publications") or []
    )
    publication_summaries = metrics.get("publications") or [
        {
            "publication_id": item.get("provider_id"),
            "publication_name": item.get("name"),
            "provider": item.get("provider"),
            "active_subscribers": ((item.get("metrics") or {}).get("subscribers") or {}).get("value"),
        }
        for item in normalized_publications
        if isinstance(item, dict)
    ]
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
    safe_intelligence["strongest_publication"] = intelligence.get(
        "strongest_publication"
    ) or None
    safe_intelligence["weakest_publication"] = intelligence.get(
        "weakest_publication"
    ) or None
    safe_intelligence["window"] = intelligence.get("window")
    safe_intelligence["comparison_window"] = intelligence.get("comparison_window")
    return {
        "metrics": {
            "publication_name": metrics.get("publication_name"),
            "active_subscribers": metrics.get("active_subscribers"),
            "active_free_subscribers": metrics.get("active_free_subscribers"),
            "active_premium_subscribers": metrics.get("active_premium_subscribers"),
            "avg_open_rate": metrics.get("avg_open_rate"),
            "avg_click_rate": metrics.get("avg_click_rate"),
            "latest_post": latest_post,
            "publication_count": metrics.get("publication_count"),
            "publications": publication_summaries,
            "window": metrics.get("window"),
            "metric_states": metrics.get("metric_states") or {},
        },
        "intelligence": safe_intelligence,
    }


def _latest_intelligence(
    store: TenantStore,
    tenant: TenantRecord,
    *,
    timeframe: str | None = None,
    view: str | None = None,
    provider: str | None = None,
    publication_ids: set[str] | None = None,
) -> LatestIntelligence | None:
    for record in store.list_runs(tenant.tenant_id, limit=100):
        if record.worker_id != "newsletter-intelligence" or record.status != "completed":
            continue
        result = record.result or {}
        data = result.get("data") or {}
        newsletter = data.get("newsletter_data") or {}
        publications = newsletter.get("publications") or []
        window = newsletter.get("window") or {}
        if timeframe and window.get("label") != timeframe:
            continue
        actual_view = "portfolio" if len(publications) > 1 else "publication"
        if view and actual_view != view:
            continue
        if provider and not any(item.get("provider") == provider for item in publications):
            continue
        if publication_ids:
            actual_ids = {
                str(item.get("provider_id"))
                for item in publications
                if item.get("provider_id") is not None
            }
            if not publication_ids.issubset(actual_ids):
                continue
        safe = _safe_intelligence(result)
        if safe is None:
            continue
        return {
            "run_id": record.run_id,
            "summary": result.get("summary"),
            "finished_at": record.finished_at,
            **safe,
        }
    return None


def _dashboard_payload(store: TenantStore, tenant: TenantRecord) -> DashboardOutput:
    runs = store.list_runs(tenant.tenant_id, limit=10)
    latest = _latest_intelligence(store, tenant)
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
    newsletter_ready = any(source["status"] == "verified" for source in sources)
    return {
        "workspace": {
            "name": tenant.name,
            "timezone": tenant.timezone,
            "sprite_provisioned": bool(tenant.sprite_name),
        },
        "connection_status": (
            "ready" if tenant.sprite_name and newsletter_ready else "needs_attention"
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
            "Show a concise card for the authenticated workspace’s latest intelligence. "
            "After the card, explain the remaining real-data analysis in the conversation: "
            "trends, strongest and weakest content, audience signals, recommendations, "
            "and anomalies. Do not repeat the card or invent missing insights."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            openWorldHint=False,
            destructiveHint=False,
        ),
        meta={
            "securitySchemes": read_security,
            "openai/toolInvocation/invoking": "Opening Harbor…",
            "openai/toolInvocation/invoked": "Harbor is ready.",
        },
    )
    def dashboard(ctx: Context) -> DashboardOutput:
        tenant = _tenant_for_context(ctx, store)
        return _dashboard_payload(store, tenant)

    server = MCPServer(
        "Harbor",
        title="Harbor",
        description="Run and inspect tenant-isolated AI workers.",
        instructions=(
            "Use Harbor to inspect and run workers for the authenticated workspace. "
            "Use harbor_dashboard when the user asks to see or open Harbor. "
            "After harbor_dashboard renders its concise card, use the returned data to "
            "write the deeper analysis below it in the conversation. Cover trends, "
            "strongest and weakest content, audience signals, recommendations, and "
            "anomalies when present; omit empty sections and never invent data. "
            "Tenant identity always comes from the bearer credential."
        ),
        auth=auth_settings,
        token_verifier=token_verifier,
        extensions=[apps],
    )

    @server.tool(
        name="harbor_worker_catalog",
        title="List available Harbor workers",
        description=(
            "List Harbor workers for the authenticated workspace and show whether "
            "each worker is enabled and runnable. This does not run a worker."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            openWorldHint=False,
            destructiveHint=False,
        ),
        meta={"securitySchemes": read_security},
    )
    def catalog(ctx: Context) -> WorkerCatalogOutput:
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
        title="Check Harbor workspace status",
        description=(
            "Check provisioning, enabled workers, outputs, billing entitlement, and "
            "redacted source-connection status for the authenticated workspace."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            openWorldHint=False,
            destructiveHint=False,
        ),
        meta={"securitySchemes": read_security},
    )
    def status(ctx: Context) -> StatusOutput:
        """Get safe status for the authenticated Harbor workspace."""
        tenant = _tenant_for_context(ctx, store)
        billing = store.get_billing(tenant.tenant_id)
        return {
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
        title="List enabled Harbor workers",
        description=(
            "List only the workers enabled for the authenticated workspace. This "
            "does not run a worker or change workspace settings."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            openWorldHint=False,
            destructiveHint=False,
        ),
        meta={"securitySchemes": read_security},
    )
    def enabled_workers(ctx: Context) -> EnabledWorkersOutput:
        """List workers enabled for the authenticated workspace."""
        tenant = _tenant_for_context(ctx, store)
        return {"workers": tenant.config.get("workers", [])}

    @server.tool(
        name="harbor_recent_runs",
        title="List recent Harbor runs",
        description=(
            "List recent worker runs for the authenticated workspace, including "
            "status, safe summary, attempts, timing, delivery status, and safe errors."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            openWorldHint=False,
            destructiveHint=False,
        ),
        meta={"securitySchemes": read_security},
    )
    def recent_runs(
        ctx: Context,
        limit: Annotated[int, Field(ge=1, le=100)] = 10,
    ) -> RecentRunsOutput:
        """List recent run status without exposing tenant filesystem paths."""
        tenant = _tenant_for_context(ctx, store)
        return {
            "runs": [
                _public_run(run) for run in store.list_runs(tenant.tenant_id, limit)
            ]
        }

    @server.tool(
        name="harbor_newsletter_intelligence",
        title="Get saved newsletter intelligence",
        description=(
            "Return the newest completed Newsletter Intelligence result matching an "
            "optional timeframe, publication/portfolio view, provider, and publication "
            "selection. This reads saved real-data results and never runs a worker. If "
            "found is false, offer to run Newsletter Intelligence with the same selection."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            openWorldHint=False,
            destructiveHint=False,
        ),
        meta={
            "securitySchemes": read_security,
            "ui": {"visibility": ["model", "app"]},
            "openai/widgetAccessible": True,
        },
    )
    def newsletter_intelligence(
        ctx: Context,
        timeframe: Timeframe | None = None,
        view: NewsletterView | None = None,
        provider: Annotated[
            str | None, Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
        ] = None,
        publication_ids: Annotated[list[str] | None, Field(max_length=50)] = None,
    ) -> IntelligenceQueryOutput:
        """Read a matching saved newsletter intelligence result."""
        tenant = _tenant_for_context(ctx, store)
        latest = _latest_intelligence(
            store,
            tenant,
            timeframe=timeframe,
            view=view,
            provider=provider,
            publication_ids={str(item) for item in (publication_ids or [])},
        )
        return {"found": latest is not None, "latest_intelligence": latest}

    @server.tool(
        name="harbor_run_worker",
        title="Run an enabled Harbor worker",
        description=(
            "Run one enabled worker in the authenticated workspace's private Sprite. "
            "This writes run and report state, reads the configured external source, "
            "and may send the configured report email. Retrying with the same "
            "idempotency key will not duplicate the run or delivery."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=True,
        ),
        meta={"securitySchemes": run_security},
    )
    def run_worker(
        ctx: Context,
        worker_id: Annotated[str, Field(min_length=1, max_length=100)],
        idempotency_key: Annotated[str, Field(min_length=1, max_length=255)]
        | None = None,
        timeframe: Timeframe | None = None,
        view: NewsletterView | None = None,
        provider: Annotated[
            str | None, Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
        ] = None,
        connection_ids: Annotated[list[str] | None, Field(max_length=50)] = None,
        publication_ids: Annotated[list[str] | None, Field(max_length=50)] = None,
        start_date: Annotated[
            str | None, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
        ] = None,
        end_date: Annotated[
            str | None, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
        ] = None,
        issue_limit: Annotated[int, Field(ge=1, le=1000)] = 100,
    ) -> RunWorkerOutput:
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
        if worker_id != "newsletter-intelligence" and any(
            value is not None
            for value in (
                timeframe,
                view,
                provider,
                connection_ids,
                publication_ids,
                start_date,
                end_date,
            )
        ):
            raise ValueError("newsletter selection applies only to Newsletter Intelligence")
        if timeframe == "custom" and (not start_date or not end_date):
            raise ValueError("custom timeframe requires start_date and end_date")
        if timeframe != "custom" and (start_date or end_date):
            raise ValueError("start_date and end_date require timeframe=custom")
        worker_input = (
            {
                key: value
                for key, value in {
                    "timeframe": timeframe,
                    "view": view,
                    "provider": provider,
                    "connection_ids": connection_ids,
                    "publication_ids": publication_ids,
                    "start_date": start_date,
                    "end_date": end_date,
                    "recent_posts": issue_limit,
                }.items()
                if value is not None
            }
            if worker_id == "newsletter-intelligence"
            else {}
        )
        runner = runner_factory()
        idem = idempotency_key or ("mcp_" + secrets.token_urlsafe(24))
        try:
            run_id, result = dispatch_worker(
                store,
                runner,
                tenant,
                worker_id,
                worker_input,
                idem,
                delivery_handler=DeliveryCoordinator(store, runner).deliver,
            )
        except DuplicateRun as error:
            if error.record is None:
                raise TenantStoreError("duplicate run record was not found") from error
            duplicate: RunWorkerOutput = {
                "duplicate_suppressed": True,
                **_public_run(error.record),
            }
            safe = _safe_intelligence(error.record.result or {})
            if safe is not None:
                duplicate["latest_intelligence"] = {
                    "run_id": error.record.run_id,
                    "summary": (error.record.result or {}).get("summary"),
                    "finished_at": error.record.finished_at,
                    **safe,
                }
            return duplicate
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
            response: RunWorkerOutput = _public_run(record)
            safe = _safe_intelligence(record.result or {})
            if safe is not None:
                response["latest_intelligence"] = {
                    "run_id": record.run_id,
                    "summary": (record.result or {}).get("summary"),
                    "finished_at": record.finished_at,
                    **safe,
                }
            return response
        return {
            "run_id": run_id,
            "status": result.get("status"),
            "summary": result.get("summary"),
            "attempt_count": result.get("attempts"),
            "deliveries": _public_deliveries(result.get("deliveries")),
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
