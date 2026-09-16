"""Minimal authenticated customer web surface for Harbor.

The portal is deliberately a thin adapter over the same tenant store, Sprite
runner, scheduler, dispatch, and output code used by the API and MCP surface.
It never accepts provider credentials or tenant filesystem paths.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import os
import re
import secrets
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .billing import (
    PLANS,
    BillingError,
    StripeBillingClient,
    apply_stripe_event,
    billing_is_active,
    billing_required,
)
from .composio_client import (
    ComposioClient,
    ComposioError,
    stable_harbor_connection_id,
)
from .dispatch import DuplicateRun, RunExecutionFailed, dispatch_worker
from .outputs import (
    DeliveryCoordinator,
    DeliveryError,
    OutputMessage,
    ResendEmailAdapter,
    validate_email_recipient,
)
from .scheduler import DailySchedule, next_occurrence
from .tenant_store import TenantStore, TenantStoreError, WebSession

SESSION_COOKIE = "harbor_session"
CSRF_COOKIE = "harbor_csrf"
COOKIE_MAX_AGE = 30 * 24 * 60 * 60


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _page(title: str, content: str, *, status_code: int = 200) -> HTMLResponse:
    response = HTMLResponse(
        """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>"""
        + _escape(title)
        + """ · Harbor</title><style>
:root{color-scheme:light;--ink:#10233f;--muted:#607089;--line:#dce4ee;--brand:#175cd3;--ok:#087443;--warn:#9a6700;--bad:#b42318;--bg:#f5f8fc}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,sans-serif}
main{max-width:880px;margin:0 auto;padding:40px 20px 80px}nav{display:flex;align-items:center;justify-content:space-between;margin-bottom:36px}.brand{font-size:22px;font-weight:800;letter-spacing:-.02em}footer{border-top:1px solid var(--line);margin-top:42px;padding-top:18px;color:var(--muted);font-size:13px}footer a{color:inherit;margin-right:16px}
h1{font-size:34px;line-height:1.15;margin:0 0 12px}h2{font-size:21px;margin:0 0 14px}.lede,.muted{color:var(--muted)}.lede{font-size:18px;margin:0 0 28px}
.card{background:white;border:1px solid var(--line);border-radius:14px;padding:22px;margin:18px 0;box-shadow:0 5px 18px rgba(16,35,63,.05)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:18px}.grid .card{margin:0}
label{display:block;font-weight:650;margin:14px 0 5px}input,select{width:100%;font:inherit;padding:10px 12px;border:1px solid #b9c6d6;border-radius:8px;background:#fff}input[type=checkbox]{width:auto;margin-right:8px}
button,.button{display:inline-block;border:0;border-radius:8px;padding:10px 15px;background:var(--brand);color:#fff;font:inherit;font-weight:700;text-decoration:none;cursor:pointer;margin-top:16px}.secondary{background:#e8eef8;color:var(--ink)}
.status{font-weight:750}.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}.notice{border-left:4px solid var(--brand);padding:12px 14px;background:#eef4ff;border-radius:6px;margin:18px 0}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px 6px;border-bottom:1px solid var(--line);font-size:14px}code{overflow-wrap:anywhere}.steps li{margin:8px 0}.secret{background:#f2f4f7;border:1px solid var(--line);padding:12px;border-radius:8px;font-family:ui-monospace,monospace;overflow-wrap:anywhere}
form.inline{display:inline}form.inline button{margin:0}.actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.small{font-size:13px}
</style></head><body><main><nav><div class="brand">Harbor</div></nav>"""
        + content
        + '<footer><a href="/privacy">Privacy</a><a href="/terms">Terms</a><a href="/support">Support</a><a href="/status">Service status</a></footer></main></body></html>',
        status_code=status_code,
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; "
        "form-action 'self' https://connect.composio.dev https://dashboard.composio.dev; "
        "base-uri 'none'; frame-ancestors 'none'"
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def _set_session_cookies(
    response: HTMLResponse | RedirectResponse, token: str, csrf_token: str
) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def _clear_session_cookies(response: HTMLResponse | RedirectResponse) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True)
    response.delete_cookie(CSRF_COOKIE, path="/", secure=True, httponly=True)


def _session(request: Request, store: TenantStore) -> WebSession | None:
    return store.resolve_web_session(request.cookies.get(SESSION_COOKIE, ""))


def _require_csrf(
    request: Request, store: TenantStore, session: WebSession, csrf_token: str
) -> bool:
    cookie_token = request.cookies.get(CSRF_COOKIE, "")
    return (
        bool(cookie_token)
        and secrets.compare_digest(cookie_token, csrf_token)
        and store.verify_web_csrf(session, csrf_token)
    )


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")[:40] or "workspace"


def _tenant_id(workspace_name: str) -> str:
    return f"{_slug(workspace_name)}-{secrets.token_hex(4)}"[:64]


def _timezone_options(selected: str) -> str:
    zones = (
        "UTC",
        "America/Los_Angeles",
        "America/Denver",
        "America/Chicago",
        "America/New_York",
        "America/Toronto",
        "America/Sao_Paulo",
        "Europe/London",
        "Europe/Paris",
        "Europe/Berlin",
        "Africa/Johannesburg",
        "Asia/Dubai",
        "Asia/Kolkata",
        "Asia/Singapore",
        "Asia/Tokyo",
        "Australia/Sydney",
        "Pacific/Auckland",
    )
    if selected not in zones:
        zones = (selected, *zones)
    return "".join(
        f'<option value="{_escape(zone)}" {"selected" if zone == selected else ""}>{_escape(zone.replace("_", " "))}</option>'
        for zone in zones
    )


def _valid_gateway(connection_id: str, gateway_base_url: str) -> bool:
    parsed = urlsplit(gateway_base_url)
    expected = re.compile(rf"^/v1/gateway/[a-z0-9_-]+/{re.escape(connection_id)}/?$")
    return bool(
        parsed.scheme == "https"
        and parsed.hostname == "api.sprites.dev"
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
        and expected.fullmatch(parsed.path)
    )


def _connection_spec(record: Any) -> dict[str, Any]:
    return {
        "tenant_id": record.tenant_id,
        "name": record.name,
        "timezone": record.timezone,
        "workspace": "/workspace",
        "workers": record.config.get("workers", []),
        "outputs": record.config.get("outputs", ["files"]),
        "connections": record.config.get("connections", []),
        "provider": "beehiiv",
    }


def _connection_form(
    connection: dict[str, Any] | None,
    publication_choices: list[dict[str, Any]],
    csrf_token: str,
    sprite_ready: bool,
) -> str:
    if connection and connection.get("status") == "verified":
        name = (connection.get("settings") or {}).get("publication_name")
        return (
            '<p class="status ok">Connected and verified</p>'
            + (f"<p>{_escape(name)}</p>" if name else "")
            + '<p class="muted small">The credential is encrypted by Fly and is not available to Harbor or the worker.</p>'
        )
    if publication_choices:
        options = "".join(
            f'<option value="{_escape(item.get("id", ""))}">{_escape(item.get("name") or "Unnamed newsletter")}</option>'
            for item in publication_choices
        )
        return f"""<p>Choose the newsletter Harbor should analyze.</p>
<form method="post" action="/app/publication"><input type="hidden" name="csrf_token" value="{_escape(csrf_token)}">
<label for="publication_id">Newsletter</label><select id="publication_id" name="publication_id" required>{options}</select>
<button type="submit">Use this newsletter</button></form>"""
    disabled = " disabled" if not sprite_ready else ""
    return f"""<p>Paste your beehiiv API key once. Harbor sends it directly to Fly’s encrypted connector store and never saves it in Harbor, your private worker, reports, or logs.</p>
<p class="muted small">In beehiiv, open Settings → Integrations → API, then copy an active API key.</p>
<form method="post" action="/app/connection"><input type="hidden" name="csrf_token" value="{_escape(csrf_token)}">
<label for="api_key">beehiiv API key</label><input id="api_key" name="api_key" type="password" required minlength="8" maxlength="4096" autocomplete="new-password"{disabled}>
<button type="submit"{disabled}>Connect beehiiv</button></form>"""


def _kit_connection_form(
    connection: dict[str, Any] | None,
    csrf_token: str,
    *,
    billing_gate: bool,
) -> str:
    if connection and connection.get("status") == "verified":
        name = (connection.get("settings") or {}).get("publication_name")
        return (
            '<p class="status ok">Connected and verified</p>'
            + (f"<p>{_escape(name)}</p>" if name else "")
            + '<p class="muted small">Kit manages consent. Composio stores and refreshes the OAuth credential; Harbor and your private worker never receive it.</p>'
        )
    composio = ComposioClient()
    if not composio.configured_for_kit():
        return '<p class="muted">Kit connections are not enabled in this Harbor environment yet.</p>'
    disabled = " disabled" if billing_gate else ""
    return f"""<p>Connect Kit with its secure sign-in screen. You will never paste an API key into Harbor.</p>
<form method="post" action="/app/connections/kit"><input type="hidden" name="csrf_token" value="{_escape(csrf_token)}">
<button type="submit"{disabled}>Connect Kit</button></form>"""


def _provision(store: TenantStore, runner: Any, tenant_id: str) -> bool:
    record = store.get(tenant_id)
    sprite_name = (
        record.sprite_name
        or (
            f"harbor-{_slug(tenant_id)}-{hashlib.sha256(tenant_id.encode()).hexdigest()[:8]}"
        )[:63]
    )
    store.record_provisioning_status(
        tenant_id, "provisioning", actor_type="web_onboarding"
    )
    try:
        runner.provision(sprite_name)
        store.set_sprite(tenant_id, sprite_name, actor_type="web_onboarding")
        store.record_provisioning_status(
            tenant_id, "ready", actor_type="web_onboarding"
        )
        return True
    except Exception as error:  # noqa: BLE001 - infrastructure adapter boundary
        store.record_provisioning_status(
            tenant_id,
            "failed",
            error_type=type(error).__name__,
            actor_type="web_onboarding",
        )
        return False


def _notice(value: str | None) -> str:
    messages = {
        "schedule_saved": "Your delivery schedule was saved.",
        "source_invalid": "That report source is not verified in this workspace. Choose a connected source and try again.",
        "email_saved": "Your email delivery setting was saved.",
        "connection_ready": "Your beehiiv connection was verified.",
        "connection_select": "Your beehiiv account is connected. Choose the newsletter Harbor should analyze.",
        "connection_failed": "Harbor could not verify that beehiiv connection. Your credential was not saved by Harbor; check that the key is active and try again.",
        "kit_ready": "Your Kit connection was verified.",
        "kit_failed": "Harbor could not verify the Kit connection. No provider credential was exposed to Harbor; please try again.",
        "run_completed": "Newsletter Intelligence completed successfully.",
        "run_failed": "The run failed and Harbor recorded the failure. You can safely try again.",
        "sprite_ready": "Your private Harbor computer is ready.",
        "sprite_failed": "Provisioning failed and was recorded. You can safely retry.",
        "csrf_failed": "That form expired. Refresh this page and try again.",
        "billing_success": "Payment received. Harbor is activating your workspace now.",
        "billing_canceled": "Checkout was canceled. Nothing was charged.",
        "billing_failed": "Billing could not be opened. Please try again.",
    }
    message = messages.get(value or "")
    return f'<div class="notice">{_escape(message)}</div>' if message else ""


def _requires_active_billing(store: TenantStore, record: Any) -> bool:
    return bool(record.config.get("billing_required")) and not billing_is_active(
        store.get_billing(record.tenant_id)
    )


def _pricing_cards(csrf_token: str, billing: Any | None) -> str:
    current = (
        f'<p class="status ok">Current plan: {_escape(billing.plan.title())}</p>'
        if billing_is_active(billing)
        else '<p class="status warn">Choose a plan to activate Harbor.</p>'
    )
    cards = "".join(
        f"""<section class="card"><h2>{_escape(plan.name)}</h2><p class="lede">${plan.monthly_dollars}/month</p>
<p>{"1 source" if plan.source_limit == 1 else ("Up to 3 sources" if plan.source_limit == 3 else "Expanded sources and API access")}</p>
<form method="post" action="/app/billing/checkout"><input type="hidden" name="csrf_token" value="{_escape(csrf_token)}"><input type="hidden" name="plan" value="{_escape(plan.id)}"><button type="submit">Choose {_escape(plan.name)}</button></form></section>"""
        for plan in PLANS
    )
    portal = (
        f"""<form method="post" action="/app/billing/portal"><input type="hidden" name="csrf_token" value="{_escape(csrf_token)}"><button class="secondary" type="submit">Manage billing</button></form>"""
        if billing and billing.stripe_customer_id
        else ""
    )
    return current + f'<div class="grid">{cards}</div>' + portal


def _send_access_code(
    email: str, code: str, *, purpose: str, idempotency_key: str
) -> None:
    if purpose == "signup":
        subject = "Verify your Harbor workspace"
        heading = "Finish creating your Harbor workspace"
    else:
        subject = "Your Harbor sign-in code"
        heading = "Sign in to Harbor"
    message = OutputMessage(
        subject=subject,
        text=f"{heading}\n\nYour one-time code is: {code}\n\nThis code expires soon. If you did not request it, ignore this email.\n",
        html=(
            '<!doctype html><html><body style="font-family:-apple-system,BlinkMacSystemFont,'
            'Segoe UI,sans-serif;line-height:1.5;color:#171717;max-width:620px;margin:auto">'
            f"<h1>{_escape(heading)}</h1><p>Your one-time code is:</p>"
            f'<p style="font-size:28px;font-weight:800;letter-spacing:3px">{_escape(code)}</p>'
            "<p>This code expires soon. If you did not request it, ignore this email.</p>"
            "</body></html>"
        ),
    )
    ResendEmailAdapter().deliver(message, [email], idempotency_key)


def create_web_router(
    store_getter: Callable[[], TenantStore],
    runner_factory: Callable[[], Any],
) -> APIRouter:
    router = APIRouter(include_in_schema=False)

    @router.get("/", response_class=HTMLResponse)
    def landing(request: Request):
        store = store_getter()
        if _session(request, store):
            return _redirect("/app")
        return _page(
            "Newsletter intelligence",
            """<h1>Your newsletter’s useful signals, every morning.</h1>
<p class="lede">Harbor securely reads your newsletter performance, runs inside your private worker computer, and delivers a concise brief.</p>
<div class="actions"><a class="button" href="/signup">Create workspace</a><a class="button secondary" href="/login">Sign in</a></div>""",
        )

    @router.get("/privacy", response_class=HTMLResponse)
    def privacy_notice():
        return _page(
            "Privacy",
            """<h1>Privacy notice</h1><p class="lede">How Harbor handles information while delivering Newsletter Intelligence.</p>
<section class="card"><h2>Information Harbor processes</h2><p>Harbor stores your account email, workspace settings, schedule, delivery destination, non-secret connection metadata, run history, delivery status, and audit events. When a worker runs, Harbor processes the newsletter performance data needed to create your report.</p></section>
<section class="card"><h2>Credentials and tenant isolation</h2><p>Provider credentials are stored by an encrypted connection service such as Fly Connectors or Composio. Harbor does not store the raw provider credential in its database, worker files, reports, or logs. Each workspace receives a separate persistent Sprite, and every operation is scoped to its workspace.</p></section>
<section class="card"><h2>Service providers</h2><p>Harbor uses infrastructure and delivery providers to operate the service, including Fly.io for application and worker compute, a hosted Postgres provider for durable state, Auth0 for ChatGPT OAuth, Composio for selected provider authorization and credential transport, and Resend for email delivery. Connected services such as beehiiv and Kit provide source data at your direction.</p></section>
<section class="card"><h2>Your choices</h2><p>You can disconnect a source, disable email delivery, or request workspace deletion. This pre-launch notice must be reviewed and paired with a support contact before public commercial release.</p><p class="muted small">Last updated September 10, 2026.</p></section>""",
        )

    @router.get("/terms", response_class=HTMLResponse)
    def terms_notice():
        return _page(
            "Terms",
            """<h1>Service terms</h1><p class="lede">Plain-language pre-launch terms for Harbor.</p>
<section class="card"><h2>The service</h2><p>Harbor connects to sources you authorize, runs enabled workers in your isolated workspace, stores run state, and delivers intelligence reports on the schedule you choose.</p></section>
<section class="card"><h2>Your responsibilities</h2><p>You must be authorized to connect each source and delivery address. Do not use Harbor to process unlawful content or to interfere with another workspace or service.</p></section>
<section class="card"><h2>Availability and outputs</h2><p>Harbor reports are informational and may contain errors. Scheduled delivery depends on connected providers and infrastructure. Failures are recorded visibly and retried according to Harbor’s operating policy.</p></section>
<section class="card"><h2>Before public launch</h2><p>These terms are a product-completeness placeholder, not a final legal agreement. Pricing, cancellation, retention, support, liability, and governing-law terms must be approved before accepting public customers.</p><p class="muted small">Last updated September 8, 2026.</p></section>""",
        )

    @router.get("/support", response_class=HTMLResponse)
    def support_page():
        support_email = os.environ.get("HARBOR_SUPPORT_EMAIL", "").strip()
        contact = (
            f'<a class="button" href="mailto:{_escape(support_email)}">Email Harbor support</a>'
            if support_email
            else '<p class="status warn">A public support contact has not been configured yet.</p>'
        )
        return _page(
            "Support",
            f"""<h1>Harbor support</h1><p class="lede">Help with workspace access, connections, runs, delivery, and billing.</p>
<section class="card"><h2>Before contacting support</h2><p>Open your Harbor workspace and note the time of the run or activity event. Never send API keys, passwords, access tokens, or connector credentials.</p>{contact}</section>
<section class="card"><h2>Service health</h2><p>Check the public <a href="/status">service status page</a> for an active platform incident.</p></section>""",
        )

    @router.get("/status", response_class=HTMLResponse)
    def public_status():
        try:
            snapshot = store_getter().operational_snapshot()
            heartbeat = snapshot["scheduler_heartbeat_status"]
            age = snapshot["scheduler_heartbeat_age_seconds"]
            scheduler_ok = heartbeat == "healthy" and age is not None and age < 300
            healthy = (
                scheduler_ok
                and snapshot["overdue_schedules"] == 0
                and snapshot["expired_run_leases"] == 0
            )
        except Exception:  # noqa: BLE001 - public health boundary
            healthy = False
            heartbeat = "unavailable"
        status = "Operational" if healthy else "Needs attention"
        css = "ok" if healthy else "bad"
        return _page(
            "Service status",
            f"""<h1>Harbor service status</h1><p class="lede status {css}">{status}</p>
<section class="card"><h2>Control plane</h2><p class="status {css}">{status}</p></section>
<section class="card"><h2>Scheduler</h2><p>{_escape(heartbeat.replace("_", " ").title())}</p></section>
<p class="muted small">This page reports aggregate service health and never exposes customer identifiers or activity.</p>""",
            status_code=200 if healthy else 503,
        )

    @router.get("/signup", response_class=HTMLResponse)
    def signup_page(request: Request):
        if _session(request, store_getter()):
            return _redirect("/app")
        return _page(
            "Create workspace",
            """<h1>Create your Harbor workspace</h1><p class="lede">Start with your email. Harbor will send a one-time verification code.</p>
<form class="card" method="post" action="/signup">
<label for="email">Email</label><input id="email" name="email" type="email" required maxlength="254" autocomplete="email">
<button type="submit">Email my code</button></form>""",
        )

    @router.post("/signup", response_class=HTMLResponse)
    def request_signup_code(email: str = Form(..., min_length=3, max_length=254)):
        store = store_getter()
        try:
            normalized_email = validate_email_recipient(email).lower()
            if store.owner_tenant_for_email(normalized_email) is not None:
                raise TenantStoreError("email already has a workspace")
            invitation, code = store.create_onboarding_invitation(
                normalized_email, expires_in_hours=1
            )
        except (TenantStoreError, DeliveryError):
            invitation = None
        if invitation is not None:
            try:
                _send_access_code(
                    normalized_email,
                    code,
                    purpose="signup",
                    idempotency_key=f"signup:{invitation.invitation_id}",
                )
            except DeliveryError:
                return _page(
                    "Email unavailable",
                    '<h1>We could not send your code</h1><p class="lede">Harbor’s email service is temporarily unavailable. Please try again.</p><a class="button" href="/signup">Try again</a>',
                    status_code=503,
                )
        # Do not disclose whether an email already owns a workspace.
        return _page(
            "Check your email",
            f"""<h1>Check your email</h1><p class="lede">If this email can create a workspace, a verification code is on its way.</p>
<a class="button" href="/onboarding?{urlencode({"email": email.strip().lower()})}">Enter verification code</a>""",
        )

    @router.get("/login", response_class=HTMLResponse)
    def login_page(request: Request):
        if _session(request, store_getter()):
            return _redirect("/app")
        return _page(
            "Sign in",
            """<h1>Sign in to Harbor</h1><p class="lede">Enter your workspace email and Harbor will send a one-time sign-in code.</p>
<form class="card" method="post" action="/login/code">
<label for="email">Email</label><input id="email" name="email" type="email" required maxlength="254" autocomplete="email">
<button type="submit">Email my sign-in code</button></form>
<p class="muted small"><a href="/login/access-key">Operator access-key sign in</a></p>""",
        )

    @router.post("/login/code", response_class=HTMLResponse)
    def request_login_code(email: str = Form(..., min_length=3, max_length=254)):
        store = store_getter()
        try:
            normalized_email = validate_email_recipient(email).lower()
            code_id, code = store.create_web_login_code(normalized_email)
        except (TenantStoreError, DeliveryError):
            code_id = None
        if code_id is not None:
            try:
                _send_access_code(
                    normalized_email,
                    code,
                    purpose="login",
                    idempotency_key=f"login:{code_id}",
                )
            except DeliveryError:
                return _page(
                    "Email unavailable",
                    '<h1>We could not send your code</h1><p class="lede">Harbor’s email service is temporarily unavailable. Please try again.</p><a class="button" href="/login">Try again</a>',
                    status_code=503,
                )
        return _page(
            "Enter sign-in code",
            f"""<h1>Enter your sign-in code</h1><p class="lede">If that email belongs to a Harbor workspace, a code is on its way.</p>
<form class="card" method="post" action="/login/verify">
<input type="hidden" name="email" value="{_escape(email.strip().lower())}">
<label for="code">One-time code</label><input id="code" name="code" required minlength="10" maxlength="10" autocomplete="one-time-code" autocapitalize="characters">
<button type="submit">Sign in</button></form>""",
        )

    @router.post("/login/verify", response_class=HTMLResponse)
    def verify_login_code(
        email: str = Form(..., min_length=3, max_length=254),
        code: str = Form(..., min_length=10, max_length=10),
    ):
        store = store_getter()
        try:
            record = store.redeem_web_login_code(email, code)
        except TenantStoreError:
            return _page(
                "Sign in",
                '<h1>That code did not work</h1><p class="lede">It may be incorrect, expired, or already used.</p><a class="button" href="/login">Request a new code</a>',
                status_code=401,
            )
        _, token, csrf_token = store.create_web_session(record.tenant_id)
        response = _redirect("/app")
        _set_session_cookies(response, token, csrf_token)
        return response

    @router.get("/login/access-key", response_class=HTMLResponse)
    def access_key_login_page():
        return _page(
            "Operator sign in",
            """<h1>Operator access-key sign in</h1><form class="card" method="post" action="/login">
<label for="tenant_id">Workspace ID</label><input id="tenant_id" name="tenant_id" required maxlength="64" autocomplete="username">
<label for="access_key">Harbor access key</label><input id="access_key" name="access_key" type="password" required autocomplete="current-password">
<button type="submit">Sign in</button></form>""",
        )

    @router.post("/login", response_class=HTMLResponse)
    def login(
        tenant_id: str = Form(..., min_length=2, max_length=64),
        access_key: str = Form(..., min_length=20, max_length=200),
    ):
        store = store_getter()
        if not store.verify_api_key(tenant_id, access_key):
            return _page(
                "Sign in",
                '<h1>Sign in failed</h1><p class="lede">That workspace ID or access key was not recognized.</p><a class="button" href="/login">Try again</a>',
                status_code=401,
            )
        _, token, csrf_token = store.create_web_session(tenant_id)
        response = _redirect("/app")
        _set_session_cookies(response, token, csrf_token)
        return response

    @router.get("/onboarding", response_class=HTMLResponse)
    def onboarding_page(request: Request, email: str = ""):
        if _session(request, store_getter()):
            return _redirect("/app")
        return _page(
            "Create workspace",
            f"""<h1>Create your Harbor workspace</h1><p class="lede">Enter the verification code from your email, then choose when Harbor should deliver your report.</p>
<form class="card" method="post" action="/onboarding">
<label for="invitation_code">Verification code</label><input id="invitation_code" name="invitation_code" required maxlength="200" autocomplete="one-time-code">
<label for="email">Email</label><input id="email" name="email" type="email" value="{_escape(email)}" required maxlength="254" autocomplete="email">
<label for="workspace_name">Workspace name</label><input id="workspace_name" name="workspace_name" required maxlength="100">
<label for="timezone">Time zone</label><select id="timezone" name="timezone" required>{_timezone_options("America/Los_Angeles")}</select>
<label for="hour">Morning report hour (0–23)</label><input id="hour" name="hour" type="number" min="0" max="23" value="6" required>
<label><input type="checkbox" checked required>Enable Newsletter Intelligence</label>
<label><input name="email_delivery" type="checkbox" value="yes" checked>Deliver reports to the invited email</label>
<button type="submit">Create workspace</button></form>""",
        )

    @router.post("/onboarding", response_class=HTMLResponse)
    def onboard(
        invitation_code: str = Form(..., min_length=20, max_length=200),
        email: str = Form(..., min_length=3, max_length=254),
        workspace_name: str = Form(..., min_length=1, max_length=100),
        timezone: str = Form(..., min_length=1, max_length=128),
        hour: int = Form(..., ge=0, le=23),
        email_delivery: str | None = Form(default=None),
    ):
        store = store_getter()
        stripe = StripeBillingClient()
        if billing_required() and not stripe.configured():
            return _page(
                "Billing unavailable",
                '<h1>Workspace signup is temporarily unavailable</h1><p class="lede">Harbor billing has not been fully configured. No workspace was created.</p>',
                status_code=503,
            )
        try:
            ZoneInfo(timezone)
            normalized_email = validate_email_recipient(email)
            schedule = {"newsletter-intelligence": {"hour": hour, "minute": 0}}
            outputs = ["files"]
            config: dict[str, Any] = {
                "workers": ["newsletter-intelligence"],
                "schedule": schedule,
                "outputs": outputs,
                "connections": [],
                "provisioning": {"status": "pending"},
                "billing_required": billing_required(),
            }
            if email_delivery == "yes":
                outputs.append("email")
                config["output_settings"] = {
                    "email": {
                        "recipients": [normalized_email],
                        "subject_prefix": "Harbor Morning Intelligence",
                    }
                }
            record, _api_key = store.redeem_onboarding_invitation(
                invitation_code,
                normalized_email,
                _tenant_id(workspace_name),
                workspace_name,
                timezone,
                config,
            )
            next_at = next_occurrence(
                dt.datetime.now(dt.timezone.utc), timezone, DailySchedule(hour, 0)
            )
            store.update_worker_schedule(
                record.tenant_id,
                "newsletter-intelligence",
                {"hour": hour, "minute": 0},
                timezone,
                next_at.isoformat(),
                actor_type="web_onboarding",
            )
        except (
            TenantStoreError,
            DeliveryError,
            ValueError,
            ZoneInfoNotFoundError,
        ) as error:
            return _page(
                "Create workspace",
                f'<h1>Workspace not created</h1><p class="lede">{_escape(error)}</p><a class="button" href="/onboarding">Try again</a>',
                status_code=400,
            )

        _, token, csrf_token = store.create_web_session(record.tenant_id)
        if record.config.get("billing_required"):
            response = _redirect("/app/billing")
            _set_session_cookies(response, token, csrf_token)
            return response

        provisioned = _provision(store, runner_factory(), record.tenant_id)
        state = (
            '<span class="status ok">Your private Harbor computer is ready.</span>'
            if provisioned
            else '<span class="status bad">Provisioning failed and was recorded. You can retry from the workspace.</span>'
        )
        response = _page(
            "Workspace created",
            f"""<h1>Your Harbor workspace is created</h1><p class="lede">{state}</p>
<div class="card"><h2>Next: connect beehiiv</h2><p>You are securely signed in. Harbor has created your workspace and private worker computer.</p></div>
<a class="button" href="/app">Continue to workspace</a>""",
        )
        _set_session_cookies(response, token, csrf_token)
        return response

    @router.get("/app", response_class=HTMLResponse)
    def dashboard(request: Request, notice: str | None = None):
        store = store_getter()
        session = _session(request, store)
        csrf_token = request.cookies.get(CSRF_COOKIE, "")
        if not session or not store.verify_web_csrf(session, csrf_token):
            response = _redirect("/login")
            _clear_session_cookies(response)
            return response
        record = store.get(session.tenant_id)
        billing = store.get_billing(record.tenant_id)
        billing_gate = _requires_active_billing(store, record)
        schedule = (record.config.get("schedule") or {}).get(
            "newsletter-intelligence", {"hour": 6, "minute": 0}
        )
        selected_source_id = schedule.get("connection_id", "")
        schedule_state = store.get_schedule_state(
            record.tenant_id, "newsletter-intelligence"
        )
        provisioning = record.config.get("provisioning") or {}
        if billing_gate:
            sprite_status = (
                '<span class="status warn">Waiting for plan activation</span>'
            )
        elif record.sprite_name:
            sprite_status = '<span class="status ok">Ready</span>'
        elif provisioning.get("status") == "failed":
            sprite_status = '<span class="status bad">Needs retry</span>'
        else:
            sprite_status = '<span class="status warn">Provisioning</span>'
        connections = record.config.get("connections", [])
        connection = next(
            (item for item in connections if item.get("provider") == "beehiiv"), None
        )
        kit_connection = next(
            (item for item in connections if item.get("provider") == "kit"), None
        )
        connected_count = sum(
            item.get("status") == "verified" for item in connections
        )
        source_options = '<option value="">All connected sources</option>' + "".join(
            f'<option value="{_escape(item["id"])}"'
            f'{" selected" if item["id"] == selected_source_id else ""}>'
            f'{_escape(item.get("provider", "Source").title())} · '
            f'{_escape((item.get("settings") or {}).get("publication_name") or item["id"])}</option>'
            for item in connections
            if item.get("status") == "verified" and item.get("id")
        )
        connection_status = (
            f'<span class="status ok">{connected_count} source{"s" if connected_count != 1 else ""} connected</span>'
            if connected_count
            else '<span class="status warn">No source connected</span>'
        )
        publication_choices = (
            (connection.get("settings") or {}).get("publications", [])
            if connection
            else []
        )
        email_config = (record.config.get("output_settings") or {}).get("email") or {}
        email_enabled = "email" in record.config.get("outputs", [])
        owner_email = store.workspace_owner_email(record.tenant_id) or ""
        runs = store.list_runs(record.tenant_id, limit=10)
        run_rows = (
            "".join(
                f"<tr><td>{_escape(run.started_at[:19].replace('T', ' '))}</td><td>{_escape(run.status)}</td><td>{_escape(run.attempt_count)}</td></tr>"
                for run in runs
            )
            or '<tr><td colspan="3" class="muted">No runs yet.</td></tr>'
        )
        audit = store.list_audit(record.tenant_id, limit=10)
        audit_rows = (
            "".join(
                f"<tr><td>{_escape(event.created_at[:19].replace('T', ' '))}</td><td>{_escape(event.action.replace('.', ' ').title())}</td></tr>"
                for event in audit
            )
            or '<tr><td colspan="2" class="muted">No activity yet.</td></tr>'
        )
        next_run = (
            _escape(schedule_state.next_run_at)
            if schedule_state
            else "Waiting for scheduler"
        )
        provisioning_action = ""
        if not record.sprite_name and not billing_gate:
            provisioning_action = f"""<form method="post" action="/app/provision"><input type="hidden" name="csrf_token" value="{_escape(csrf_token)}"><button type="submit">Retry provisioning</button></form>"""
        billing_card = ""
        if record.config.get("billing_required") or billing is not None:
            billing_status = (
                f'<span class="status ok">{_escape(billing.plan.title())} · {_escape(billing.status.title())}</span>'
                if billing_is_active(billing)
                else '<span class="status warn">Plan required</span>'
            )
            billing_card = f'<section class="card"><h2>Plan</h2><p>{billing_status}</p><a class="button secondary" href="/app/billing">View billing</a></section>'
        run_operation = "web_" + secrets.token_urlsafe(24)
        content = f"""<h1>{_escape(record.name)}</h1><p class="lede">Newsletter Intelligence workspace</p>{_notice(notice)}
<div class="grid"><div class="card"><h2>Private worker computer</h2><p>{sprite_status}</p>{provisioning_action}</div>
<div class="card"><h2>Sources</h2><p>{connection_status}</p></div>
<div class="card"><h2>Next report</h2><p class="status">{next_run}</p></div></div>
{billing_card}

<section class="card"><h2>Connect beehiiv</h2>
{_connection_form(connection, publication_choices, csrf_token, bool(record.sprite_name) and not billing_gate)}</section>

<section class="card"><h2>Connect Kit</h2>
{_kit_connection_form(kit_connection, csrf_token, billing_gate=billing_gate)}</section>

<div class="grid"><section class="card"><h2>Schedule</h2><form method="post" action="/app/schedule"><input type="hidden" name="csrf_token" value="{_escape(csrf_token)}">
<label>Morning hour (0–23)</label><input name="hour" type="number" min="0" max="23" value="{_escape(schedule.get("hour", 6))}" required>
<label>Minute</label><input name="minute" type="number" min="0" max="59" value="{_escape(schedule.get("minute", 0))}" required>
<label>Report source</label><select name="connection_id">{source_options}</select>
<label>Time zone</label><select name="timezone" required>{_timezone_options(record.timezone)}</select><button type="submit">Save schedule</button></form></section>

<section class="card"><h2>Email output</h2><form method="post" action="/app/email"><input type="hidden" name="csrf_token" value="{_escape(csrf_token)}">
<label><input name="enabled" type="checkbox" value="yes" {"checked" if email_enabled else ""}>Send report by email</label>
<label>Recipient</label><input name="recipient" type="email" value="{_escape((email_config.get("recipients") or [owner_email])[0] if (email_config.get("recipients") or [owner_email]) else "")}" maxlength="254">
<button type="submit">Save email output</button></form></section></div>

<section class="card"><h2>Run now</h2><p>Uses the same worker and delivery path as the scheduler.</p><form method="post" action="/app/run"><input type="hidden" name="csrf_token" value="{_escape(csrf_token)}"><input type="hidden" name="idempotency_key" value="{_escape(run_operation)}"><button type="submit" {"disabled" if not record.sprite_name or billing_gate else ""}>Run Newsletter Intelligence</button></form></section>

<section class="card"><h2>Recent runs</h2><table><thead><tr><th>Started (UTC)</th><th>Status</th><th>Attempts</th></tr></thead><tbody>{run_rows}</tbody></table></section>
<section class="card"><h2>Workspace activity</h2><table><thead><tr><th>Time (UTC)</th><th>Event</th></tr></thead><tbody>{audit_rows}</tbody></table></section>
<form method="post" action="/logout"><input type="hidden" name="csrf_token" value="{_escape(csrf_token)}"><button class="secondary" type="submit">Sign out</button></form>"""
        return _page(record.name, content)

    def authenticated_form(
        request: Request, csrf_token: str
    ) -> tuple[TenantStore, WebSession] | None:
        store = store_getter()
        session = _session(request, store)
        if not session or not _require_csrf(request, store, session, csrf_token):
            return None
        return store, session

    @router.get("/app/billing", response_class=HTMLResponse)
    def billing_page(request: Request, notice: str | None = None):
        store = store_getter()
        session = _session(request, store)
        csrf_token = request.cookies.get(CSRF_COOKIE, "")
        if not session or not store.verify_web_csrf(session, csrf_token):
            return _redirect("/login")
        stripe = StripeBillingClient()
        if not stripe.configured():
            return _page(
                "Billing",
                '<h1>Billing is not configured yet</h1><p class="lede">Harbor has not enabled paid checkout for this environment.</p><a class="button secondary" href="/app">Back to workspace</a>',
                status_code=503,
            )
        billing = store.get_billing(session.tenant_id)
        return _page(
            "Plans",
            f'<h1>Choose your Harbor plan</h1><p class="lede">Secure monthly billing is handled on Stripe’s hosted Checkout.</p>{_notice(notice)}'
            + _pricing_cards(csrf_token, billing)
            + '<a class="button secondary" href="/app">Back to workspace</a>',
        )

    @router.post("/app/billing/checkout")
    def billing_checkout(
        request: Request,
        csrf_token: str = Form(...),
        plan: str = Form(..., min_length=2, max_length=64),
    ):
        context = authenticated_form(request, csrf_token)
        if not context:
            return _redirect("/app?notice=csrf_failed")
        store, session = context
        record = store.get(session.tenant_id)
        billing = store.get_billing(record.tenant_id)
        email = store.workspace_owner_email(record.tenant_id)
        if not email:
            return _redirect("/app/billing?notice=billing_failed")
        try:
            url = StripeBillingClient().create_checkout(
                record.tenant_id,
                email,
                plan,
                customer_id=billing.stripe_customer_id if billing else None,
            )
        except BillingError:
            return _redirect("/app/billing?notice=billing_failed")
        return RedirectResponse(url, status_code=303)

    @router.post("/app/billing/portal")
    def billing_portal(request: Request, csrf_token: str = Form(...)):
        context = authenticated_form(request, csrf_token)
        if not context:
            return _redirect("/app?notice=csrf_failed")
        store, session = context
        billing = store.get_billing(session.tenant_id)
        try:
            url = StripeBillingClient().create_portal(
                billing.stripe_customer_id if billing else ""
            )
        except BillingError:
            return _redirect("/app/billing?notice=billing_failed")
        return RedirectResponse(url, status_code=303)

    @router.post("/stripe/webhook")
    async def stripe_webhook(request: Request):
        client = StripeBillingClient()
        try:
            event = client.verify_webhook(
                await request.body(), request.headers.get("Stripe-Signature", "")
            )
            store = store_getter()
            _applied, activated_tenant = apply_stripe_event(store, client, event)
            if activated_tenant:
                record = store.get(activated_tenant)
                if not record.sprite_name:
                    _provision(store, runner_factory(), activated_tenant)
        except (BillingError, TenantStoreError):
            return HTMLResponse("invalid webhook", status_code=400)
        return HTMLResponse("ok", status_code=200)

    @router.post("/app/provision")
    def provision(request: Request, csrf_token: str = Form(...)):
        context = authenticated_form(request, csrf_token)
        if not context:
            return _redirect("/app?notice=csrf_failed")
        store, session = context
        record = store.get(session.tenant_id)
        if _requires_active_billing(store, record):
            return _redirect("/app/billing")
        success = _provision(store, runner_factory(), session.tenant_id)
        return _redirect(
            "/app?notice=" + ("sprite_ready" if success else "sprite_failed")
        )

    @router.post("/app/schedule")
    def update_schedule(
        request: Request,
        csrf_token: str = Form(...),
        hour: int = Form(..., ge=0, le=23),
        minute: int = Form(..., ge=0, le=59),
        timezone: str = Form(..., min_length=1, max_length=128),
        connection_id: str | None = Form(default=None, max_length=255),
    ):
        context = authenticated_form(request, csrf_token)
        if not context:
            return _redirect("/app?notice=csrf_failed")
        store, session = context
        try:
            ZoneInfo(timezone)
            record = store.get(session.tenant_id)
            current_schedule = (record.config.get("schedule") or {}).get(
                "newsletter-intelligence", {}
            )
            selected_source_id = (
                current_schedule.get("connection_id", "")
                if connection_id is None
                else connection_id
            )
            if selected_source_id and not any(
                item.get("id") == selected_source_id
                and item.get("status") == "verified"
                for item in record.config.get("connections", [])
            ):
                return _redirect("/app?notice=source_invalid")
            next_at = next_occurrence(
                dt.datetime.now(dt.timezone.utc),
                timezone,
                DailySchedule(hour, minute),
            )
            store.update_worker_schedule(
                session.tenant_id,
                "newsletter-intelligence",
                {
                    "hour": hour,
                    "minute": minute,
                    **({"connection_id": selected_source_id} if selected_source_id else {}),
                },
                timezone,
                next_at.isoformat(),
                actor_type="web_portal",
            )
        except (TenantStoreError, ValueError, ZoneInfoNotFoundError):
            return _redirect("/app?notice=csrf_failed")
        return _redirect("/app?notice=schedule_saved")

    @router.post("/app/email")
    def update_email(
        request: Request,
        csrf_token: str = Form(...),
        recipient: str = Form(default="", max_length=254),
        enabled: str | None = Form(default=None),
    ):
        context = authenticated_form(request, csrf_token)
        if not context:
            return _redirect("/app?notice=csrf_failed")
        store, session = context
        try:
            recipients = (
                [validate_email_recipient(recipient)] if enabled == "yes" else []
            )
            store.configure_email_output(
                session.tenant_id,
                enabled=enabled == "yes",
                recipients=recipients,
                subject_prefix="Harbor Morning Intelligence",
                actor_type="web_portal",
            )
        except (TenantStoreError, DeliveryError):
            return _redirect("/app?notice=csrf_failed")
        return _redirect("/app?notice=email_saved")

    @router.post("/app/connections/kit")
    def start_kit_connection(request: Request, csrf_token: str = Form(...)):
        context = authenticated_form(request, csrf_token)
        if not context:
            return _redirect("/app?notice=csrf_failed")
        store, session = context
        record = store.get(session.tenant_id)
        if _requires_active_billing(store, record):
            return _redirect("/app/billing")
        billing = store.get_billing(record.tenant_id)
        active_sources = [
            item
            for item in record.config.get("connections", [])
            if item.get("status") == "verified"
        ]
        already_has_kit = any(item.get("provider") == "kit" for item in active_sources)
        if billing and not already_has_kit and len(active_sources) >= billing.source_limit:
            return _redirect("/app?notice=kit_failed")
        try:
            link = ComposioClient().create_kit_link(record.tenant_id)
        except ComposioError:
            return _redirect("/app?notice=kit_failed")
        return RedirectResponse(link["redirect_url"], status_code=303)

    @router.get("/app/connections/composio/verify")
    def complete_composio_connection(request: Request, session_uri: str = ""):
        """Composio callback identity verifier, bound to the Harbor web session."""
        store = store_getter()
        session = _session(request, store)
        if not session:
            return _redirect("/login")
        record = store.get(session.tenant_id)
        if _requires_active_billing(store, record):
            return _redirect("/app/billing")
        try:
            composio = ComposioClient()
            completed = composio.complete_auth(session_uri, record.tenant_id)
            vendor_connection_id = completed["connected_account_id"]
            composio.verify_kit_account(vendor_connection_id, record.tenant_id)
            account_payload = composio.proxy_kit_get(vendor_connection_id, "account")
            account = account_payload.get("account")
            if not isinstance(account, dict) or account.get("id") is None:
                raise ComposioError(
                    "invalid_provider_response", "Kit account metadata is missing"
                )
            billing = store.get_billing(record.tenant_id)
            existing = [
                item
                for item in record.config.get("connections", [])
                if item.get("status") == "verified" and item.get("provider") != "kit"
            ]
            if billing and len(existing) >= billing.source_limit:
                raise ComposioError("source_limit", "the plan source limit was reached")
            connection_id = stable_harbor_connection_id(record.tenant_id, "kit")
            connection = {
                "id": connection_id,
                "provider": "kit",
                "status": "pending",
                "settings": {
                    "transport": "composio",
                    "auth_mode": "composio_broker",
                    "connected_account_id": vendor_connection_id,
                    "recent_posts": 100,
                    "publication_id": str(account["id"]),
                    "publication_name": (
                        account.get("name")
                        if isinstance(account.get("name"), str)
                        else "Kit newsletter"
                    ),
                },
            }
            store.upsert_connection(
                record.tenant_id, connection, actor_type="web_portal"
            )
            store.record_connection_verification(
                record.tenant_id,
                connection_id,
                {
                    "status": "verified",
                    "provider": "kit",
                    "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "publication_id": str(account["id"]),
                    "publication_name": connection["settings"]["publication_name"],
                },
                actor_type="web_portal",
            )
        except (ComposioError, TenantStoreError):
            return _redirect("/app?notice=kit_failed")
        return _redirect("/app?notice=kit_ready")

    @router.post("/app/connection")
    def attach_connection(
        request: Request,
        csrf_token: str = Form(...),
        api_key: str = Form(..., min_length=8, max_length=4096),
    ):
        context = authenticated_form(request, csrf_token)
        if not context:
            return _redirect("/app?notice=csrf_failed")
        store, session = context
        record = store.get(session.tenant_id)
        if _requires_active_billing(store, record):
            return _redirect("/app/billing")
        billing = store.get_billing(record.tenant_id)
        if (
            billing
            and len(record.config.get("connections", [])) >= billing.source_limit
        ):
            return _redirect("/app?notice=connection_failed")
        if not record.sprite_name:
            return _redirect("/app?notice=connection_failed")
        connection_id: str | None = None
        try:
            runner = runner_factory()
            created = runner.create_beehiiv_connector(record.sprite_name, api_key)
            connection_id = created["id"]
            gateway_base_url = created["gateway_base_url"]
            if not re.fullmatch(r"[A-Za-z0-9_-]+", connection_id) or not _valid_gateway(
                connection_id, gateway_base_url
            ):
                raise TenantStoreError("Sprites returned invalid connector metadata")
            connection = {
                "id": connection_id,
                "provider": "beehiiv",
                "status": "pending",
                "settings": {
                    "recent_posts": 5,
                    "gateway_base_url": gateway_base_url,
                    "auth_mode": "sprite_connector",
                },
            }
            record = store.upsert_connection(
                session.tenant_id, connection, actor_type="web_portal"
            )
            result = runner.verify_connection(
                record.sprite_name,
                _connection_spec(record),
            )
            publications = result.get("publications") or []
            if len(publications) == 1:
                connection["settings"]["publication_id"] = publications[0]["id"]
                connection["settings"]["publication_name"] = publications[0].get("name")
                record = store.upsert_connection(
                    session.tenant_id, connection, actor_type="web_portal"
                )
                result = runner.verify_connection(
                    record.sprite_name, _connection_spec(record)
                )
                store.record_connection_verification(
                    session.tenant_id, connection_id, result, actor_type="web_portal"
                )
                if result.get("status") != "verified":
                    return _redirect("/app?notice=connection_failed")
            elif len(publications) > 1:
                connection["status"] = "selection_required"
                connection["settings"]["publications"] = publications
                store.upsert_connection(
                    session.tenant_id, connection, actor_type="web_portal"
                )
                return _redirect("/app?notice=connection_select")
            else:
                raise TenantStoreError("beehiiv returned no publications")
        except Exception as error:  # noqa: BLE001 - connector adapter boundary
            result = {
                "status": "failed",
                "error": {
                    "kind": type(error).__name__,
                    "detail": "connection verification failed",
                },
            }
            try:
                if connection_id is None:
                    raise TenantStoreError("connector was not created")
                store.record_connection_verification(
                    session.tenant_id,
                    connection_id,
                    result,
                    actor_type="web_portal",
                )
            except TenantStoreError:
                pass
            return _redirect("/app?notice=connection_failed")
        return _redirect("/app?notice=connection_ready")

    @router.post("/app/publication")
    def select_publication(
        request: Request,
        csrf_token: str = Form(...),
        publication_id: str = Form(..., min_length=1, max_length=255),
    ):
        context = authenticated_form(request, csrf_token)
        if not context:
            return _redirect("/app?notice=csrf_failed")
        store, session = context
        try:
            record = store.get(session.tenant_id)
            connection = next(
                item
                for item in record.config.get("connections", [])
                if item.get("provider") == "beehiiv"
            )
            choices = (connection.get("settings") or {}).get("publications", [])
            selected = next(
                item for item in choices if item.get("id") == publication_id
            )
            settings = dict(connection.get("settings") or {})
            settings.pop("publications", None)
            settings["publication_id"] = publication_id
            settings["publication_name"] = selected.get("name")
            connection = {**connection, "status": "pending", "settings": settings}
            record = store.upsert_connection(
                session.tenant_id, connection, actor_type="web_portal"
            )
            result = runner_factory().verify_connection(
                record.sprite_name, _connection_spec(record)
            )
            store.record_connection_verification(
                session.tenant_id, connection["id"], result, actor_type="web_portal"
            )
            if result.get("status") != "verified":
                return _redirect("/app?notice=connection_failed")
        except (StopIteration, TenantStoreError):
            return _redirect("/app?notice=connection_failed")
        return _redirect("/app?notice=connection_ready")

    @router.post("/app/run")
    def run_worker(
        request: Request,
        csrf_token: str = Form(...),
        idempotency_key: str = Form(..., min_length=20, max_length=255),
    ):
        context = authenticated_form(request, csrf_token)
        if not context:
            return _redirect("/app?notice=csrf_failed")
        store, session = context
        record = store.get(session.tenant_id)
        if _requires_active_billing(store, record):
            return _redirect("/app/billing")
        if not record.sprite_name:
            return _redirect("/app?notice=run_failed")
        schedule = (record.config.get("schedule") or {}).get(
            "newsletter-intelligence", {}
        )
        source_id = schedule.get("connection_id")
        if source_id and not any(
            item.get("id") == source_id and item.get("status") == "verified"
            for item in record.config.get("connections", [])
        ):
            return _redirect("/app?notice=run_failed")
        runner = runner_factory()
        try:
            dispatch_worker(
                store,
                runner,
                record,
                "newsletter-intelligence",
                {"connection_id": source_id} if source_id else {},
                idempotency_key,
                delivery_handler=DeliveryCoordinator(store, runner).deliver,
            )
        except DuplicateRun:
            existing = next(
                (
                    run
                    for run in store.list_runs(session.tenant_id)
                    if run.idempotency_key == idempotency_key
                ),
                None,
            )
            return _redirect(
                "/app?notice="
                + (
                    "run_completed"
                    if existing and existing.status == "completed"
                    else "run_failed"
                )
            )
        except (RunExecutionFailed, TenantStoreError):
            return _redirect("/app?notice=run_failed")
        return _redirect("/app?notice=run_completed")

    @router.post("/logout")
    def logout(request: Request, csrf_token: str = Form(...)):
        store = store_getter()
        session = _session(request, store)
        token = request.cookies.get(SESSION_COOKIE, "")
        if session and _require_csrf(request, store, session, csrf_token):
            store.delete_web_session(token)
        response = _redirect("/")
        _clear_session_cookies(response)
        return response

    return router
