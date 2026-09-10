"""Narrow Composio infrastructure adapter.

Harbor uses Composio for hosted OAuth and authenticated provider transport. It
does not expose Composio tools to workers, models, or remote MCP users.
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any
from urllib.parse import urlsplit

import httpx


class ComposioError(RuntimeError):
    def __init__(self, kind: str, detail: str):
        self.kind = kind
        self.detail = detail
        super().__init__(f"{kind}: {detail}")


_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,255}$")
_KIT_OPERATIONS: dict[str, tuple[str, frozenset[str]]] = {
    "account": ("/v4/account", frozenset()),
    "subscribers": (
        "/v4/subscribers",
        frozenset({"status", "include_total_count", "per_page", "slim", "after"}),
    ),
    "growth-stats": (
        "/v4/account/growth_stats",
        frozenset({"starting", "ending"}),
    ),
    "broadcast-stats": (
        "/v4/broadcasts/stats",
        frozenset(
            {
                "after",
                "include_total_count",
                "per_page",
                "sent_after",
                "sent_before",
                "status",
            }
        ),
    ),
    "tags": ("/v4/tags", frozenset({"include", "per_page", "after"})),
}


def stable_composio_user_id(tenant_id: str) -> str:
    """Return a stable opaque vendor user ID derived only from Harbor identity."""
    return "harbor_" + hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()[:40]


def stable_harbor_connection_id(tenant_id: str, provider: str) -> str:
    """Keep Harbor identity stable when a vendor account is reconnected."""
    digest = hashlib.sha256(f"{tenant_id}:{provider}".encode()).hexdigest()[:20]
    return f"{provider}-{digest}"


class ComposioClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        api_base: str | None = None,
        kit_auth_config_id: str | None = None,
        http_client: httpx.Client | None = None,
        zdr_confirmed: bool | None = None,
        callback_verification_confirmed: bool | None = None,
    ):
        self.api_key = api_key or os.environ.get("COMPOSIO_API_KEY", "")
        self.api_base = (
            api_base or os.environ.get("COMPOSIO_API_URL") or "https://backend.composio.dev"
        ).rstrip("/")
        self.kit_auth_config_id = kit_auth_config_id or os.environ.get(
            "HARBOR_COMPOSIO_KIT_AUTH_CONFIG_ID", ""
        )
        self.zdr_confirmed = (
            zdr_confirmed
            if zdr_confirmed is not None
            else os.environ.get("HARBOR_COMPOSIO_ZDR_CONFIRMED") == "1"
        )
        self.callback_verification_confirmed = (
            callback_verification_confirmed
            if callback_verification_confirmed is not None
            else os.environ.get("HARBOR_COMPOSIO_CALLBACK_VERIFICATION_CONFIRMED")
            == "1"
        )
        self._http = http_client

    def configured_for_kit(self) -> bool:
        return bool(
            self.api_key
            and self.kit_auth_config_id
            and self.zdr_confirmed
            and self.callback_verification_confirmed
        )

    def _require_api_key(self) -> None:
        if not self.api_key:
            raise ComposioError("not_configured", "Composio is not configured")
        if not self.zdr_confirmed:
            raise ComposioError(
                "privacy_not_confirmed",
                "Composio zero-data-retention must be enabled before Harbor can use it",
            )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._require_api_key()
        try:
            request_args = {
                "json": json_body,
                "headers": {
                    "x-api-key": self.api_key,
                    "Accept": "application/json",
                },
            }
            if self._http is not None:
                response = self._http.request(
                    method, f"{self.api_base}{path}", **request_args
                )
            else:
                with httpx.Client(timeout=60.0, follow_redirects=False) as client:
                    response = client.request(
                        method, f"{self.api_base}{path}", **request_args
                    )
        except httpx.RequestError as error:
            raise ComposioError("composio_unreachable", "credential service is unavailable") from error
        if response.status_code < 200 or response.status_code >= 300:
            # The body is intentionally omitted: upstream errors may contain
            # provider material or other customer-specific values.
            raise ComposioError(
                "composio_http_error",
                f"credential service returned HTTP {response.status_code}",
            )
        try:
            payload = response.json()
        except ValueError as error:
            raise ComposioError("invalid_composio_response", "response is not JSON") from error
        if not isinstance(payload, dict):
            raise ComposioError("invalid_composio_response", "response must be an object")
        return payload

    def create_kit_link(self, tenant_id: str) -> dict[str, str]:
        if not self.configured_for_kit():
            raise ComposioError(
                "not_configured",
                "Kit connection is unavailable until Composio privacy and callback verification are configured",
            )
        payload = self._request(
            "POST",
            "/api/v3.1/connected_accounts/link",
            json_body={
                "auth_config_id": self.kit_auth_config_id,
                "user_id": stable_composio_user_id(tenant_id),
            },
        )
        connection_id = payload.get("connected_account_id")
        redirect_url = payload.get("redirect_url")
        if not isinstance(connection_id, str) or not _ID_PATTERN.fullmatch(connection_id):
            raise ComposioError("invalid_composio_response", "connection id is invalid")
        if not isinstance(redirect_url, str):
            raise ComposioError("invalid_composio_response", "connection URL is missing")
        parsed = urlsplit(redirect_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not parsed.hostname.endswith(".composio.dev")
            or parsed.username
            or parsed.password
        ):
            raise ComposioError("invalid_composio_response", "connection URL is invalid")
        return {"connected_account_id": connection_id, "redirect_url": redirect_url}

    def complete_auth(self, session_uri: str, tenant_id: str) -> dict[str, str]:
        if not self.callback_verification_confirmed:
            raise ComposioError(
                "not_configured", "Composio callback identity verification is not configured"
            )
        if not session_uri or len(session_uri) > 4096:
            raise ComposioError("invalid_callback", "connection callback is invalid")
        payload = self._request(
            "POST",
            "/api/v3.1/connected_accounts/complete_auth",
            json_body={
                "session_uri": session_uri,
                "user_id": stable_composio_user_id(tenant_id),
            },
        )
        connection_id = payload.get("connected_account_id") or payload.get("id")
        toolkit = payload.get("toolkit_slug")
        if toolkit is None and isinstance(payload.get("toolkit"), dict):
            toolkit = payload["toolkit"].get("slug")
        if not isinstance(connection_id, str) or not _ID_PATTERN.fullmatch(connection_id):
            raise ComposioError("invalid_composio_response", "connection id is invalid")
        if str(toolkit).lower() != "kit":
            raise ComposioError("wrong_toolkit", "the completed connection is not Kit")
        return {"connected_account_id": connection_id, "toolkit": "kit"}

    def get_connected_account(self, connection_id: str) -> dict[str, Any]:
        if not _ID_PATTERN.fullmatch(connection_id):
            raise ComposioError("invalid_connection", "connection id is invalid")
        return self._request("GET", f"/api/v3.1/connected_accounts/{connection_id}")

    def verify_kit_account(self, connection_id: str, tenant_id: str) -> dict[str, Any]:
        account = self.get_connected_account(connection_id)
        toolkit = account.get("toolkit") or {}
        if (
            str(account.get("status")).upper() != "ACTIVE"
            or not isinstance(toolkit, dict)
            or str(toolkit.get("slug")).lower() != "kit"
            or account.get("user_id") != stable_composio_user_id(tenant_id)
        ):
            raise ComposioError(
                "connection_not_active", "the tenant's Kit connection is not active"
            )
        return account

    def proxy_kit_get(
        self,
        connection_id: str,
        operation: str,
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not _ID_PATTERN.fullmatch(connection_id):
            raise ComposioError("invalid_connection", "connection id is invalid")
        try:
            endpoint, allowed_query = _KIT_OPERATIONS[operation]
        except KeyError as error:
            raise ComposioError("operation_not_allowed", "Kit operation is not allowed") from error
        query = query or {}
        if any(key not in allowed_query for key in query):
            raise ComposioError("parameter_not_allowed", "Kit query parameter is not allowed")
        parameters = [
            {"name": key, "value": str(value), "in": "query"}
            for key, value in query.items()
            if value is not None
        ]
        payload = self._request(
            "POST",
            "/api/v3.1/tools/execute/proxy",
            json_body={
                "connected_account_id": connection_id,
                "endpoint": endpoint,
                "method": "GET",
                "parameters": parameters,
            },
        )
        try:
            provider_status = int(payload.get("status"))
        except (TypeError, ValueError) as error:
            raise ComposioError(
                "invalid_composio_response", "provider status is missing"
            ) from error
        if provider_status < 200 or provider_status >= 300:
            raise ComposioError(
                "kit_http_error", f"provider returned HTTP {provider_status}"
            )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ComposioError("invalid_composio_response", "provider response is invalid")
        return data


def kit_operations() -> frozenset[str]:
    return frozenset(_KIT_OPERATIONS)
