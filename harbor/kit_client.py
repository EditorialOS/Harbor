"""Kit API v4 client for newsletter intelligence.

Production OAuth access tokens are injected by a tenant-scoped Sprite
Connector. Direct bearer/API-key modes exist for controlled local verification;
Harbor never persists their plaintext values.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

KIT_BASE = os.environ.get("KIT_API_BASE", "https://api.kit.com/v4")

_BROKER_OPERATIONS = {
    "/account": "account",
    "/subscribers": "subscribers",
    "/account/growth_stats": "growth-stats",
    "/broadcasts/stats": "broadcast-stats",
    "/tags": "tags",
}


class KitError(Exception):
    def __init__(self, kind: str, detail: str):
        self.kind = kind
        self.detail = detail
        super().__init__(f"{kind}: {detail}")


def normalize_rate(value: Any) -> float | None:
    """Normalize Kit's percentage-shaped rates to 0..1 ratios."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise KitError("invalid_provider_response", "rate is not numeric") from error
    if number < 0:
        raise KitError("invalid_provider_response", "rate cannot be negative")
    return number / 100 if number > 1 else number


def _get(
    path: str,
    params: dict[str, Any] | None = None,
    *,
    credential: str | None,
    base_url: str = KIT_BASE,
    auth_mode: str = "oauth_bearer",
) -> dict[str, Any]:
    if auth_mode == "harbor_broker":
        try:
            operation = _BROKER_OPERATIONS[path]
        except KeyError as error:
            raise KitError("operation_not_allowed", "Kit operation is not allowed") from error
        url = f"{base_url.rstrip('/')}/{operation}"
    else:
        url = f"{base_url.rstrip('/')}{path}"
    if params:
        filtered = {key: value for key, value in params.items() if value is not None}
        if filtered:
            url += "?" + urllib.parse.urlencode(filtered, doseq=True)
    headers = {"Accept": "application/json"}
    if auth_mode == "oauth_bearer":
        if not credential:
            raise KitError("missing_credential", "Kit OAuth credential is required")
        headers["Authorization"] = f"Bearer {credential}"
    elif auth_mode == "api_key":
        if not credential:
            raise KitError("missing_credential", "Kit API key is required")
        headers["X-Kit-Api-Key"] = credential
    elif auth_mode == "harbor_broker":
        if not credential:
            raise KitError(
                "missing_credential", "Harbor broker authorization is required"
            )
        headers["Authorization"] = f"Bearer {credential}"
    elif auth_mode != "sprite_connector":
        raise KitError("invalid_auth_mode", auth_mode)

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise KitError(
            "kit_http_error", f"provider returned HTTP {error.code}"
        ) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise KitError("kit_unreachable", str(error)) from error
    except json.JSONDecodeError as error:
        raise KitError("invalid_provider_response", "response is not JSON") from error
    if not isinstance(payload, dict):
        raise KitError("invalid_provider_response", "response must be an object")
    return payload


def current_account(
    *,
    credential: str | None = None,
    base_url: str | None = None,
    auth_mode: str = "oauth_bearer",
) -> dict[str, str | None]:
    payload = _get(
        "/account",
        credential=credential,
        base_url=base_url or KIT_BASE,
        auth_mode=auth_mode,
    )
    account = payload.get("account")
    if not isinstance(account, dict) or account.get("id") is None:
        raise KitError("invalid_provider_response", "account is missing")
    timezone = account.get("timezone") or {}
    return {
        "account_id": str(account["id"]),
        "account_name": account.get("name")
        if isinstance(account.get("name"), str)
        else None,
        "timezone": timezone.get("name") if isinstance(timezone, dict) else None,
    }


def active_subscriber_count(
    *,
    credential: str | None = None,
    base_url: str | None = None,
    auth_mode: str = "oauth_bearer",
) -> int | None:
    payload = _get(
        "/subscribers",
        {
            "status": "active",
            "include_total_count": "true",
            "per_page": 1,
            "slim": "true",
        },
        credential=credential,
        base_url=base_url or KIT_BASE,
        auth_mode=auth_mode,
    )
    pagination = payload.get("pagination") or {}
    total = payload.get("total_count")
    if total is None and isinstance(pagination, dict):
        total = pagination.get("total_count")
    if total is None:
        return None
    try:
        return int(total)
    except (TypeError, ValueError) as error:
        raise KitError(
            "invalid_provider_response", "subscriber total is not numeric"
        ) from error


def growth_stats(
    *,
    starting: str,
    ending: str,
    credential: str | None = None,
    base_url: str | None = None,
    auth_mode: str = "oauth_bearer",
) -> dict[str, Any]:
    payload = _get(
        "/account/growth_stats",
        {"starting": starting, "ending": ending},
        credential=credential,
        base_url=base_url or KIT_BASE,
        auth_mode=auth_mode,
    )
    stats = payload.get("stats")
    if not isinstance(stats, dict):
        raise KitError("invalid_provider_response", "growth stats are missing")
    return stats


def broadcast_stats(
    *,
    limit: int = 100,
    sent_after: str | None = None,
    sent_before: str | None = None,
    credential: str | None = None,
    base_url: str | None = None,
    auth_mode: str = "oauth_bearer",
) -> dict[str, Any]:
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")
    rows: list[dict[str, Any]] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()
    total_count: int | None = None
    while len(rows) < limit:
        payload = _get(
            "/broadcasts/stats",
            {
                "after": cursor,
                "include_total_count": "true" if cursor is None else None,
                "per_page": min(1000, limit - len(rows)),
                "sent_after": sent_after,
                "sent_before": sent_before,
                "status": "completed",
            },
            credential=credential,
            base_url=base_url or KIT_BASE,
            auth_mode=auth_mode,
        )
        page = payload.get("broadcasts")
        pagination = payload.get("pagination") or {}
        if not isinstance(page, list) or not isinstance(pagination, dict):
            raise KitError("invalid_provider_response", "broadcast page is invalid")
        rows.extend(item for item in page if isinstance(item, dict))
        if total_count is None:
            candidate = payload.get("total_count", pagination.get("total_count"))
            if candidate is not None:
                try:
                    total_count = int(candidate)
                except (TypeError, ValueError) as error:
                    raise KitError(
                        "invalid_provider_response", "broadcast total is not numeric"
                    ) from error
        if not pagination.get("has_next_page"):
            break
        next_cursor = pagination.get("end_cursor")
        if not isinstance(next_cursor, str) or next_cursor in seen_cursors:
            raise KitError("invalid_provider_response", "broadcast cursor is invalid")
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    return {"broadcasts": rows[:limit], "total_count": total_count}


def list_tags(
    *,
    credential: str | None = None,
    base_url: str | None = None,
    auth_mode: str = "oauth_bearer",
) -> list[dict[str, Any]]:
    payload = _get(
        "/tags",
        {"include": "subscriber_count", "per_page": 1000},
        credential=credential,
        base_url=base_url or KIT_BASE,
        auth_mode=auth_mode,
    )
    rows = payload.get("tags")
    if not isinstance(rows, list):
        raise KitError("invalid_provider_response", "tags are invalid")
    return [
        {
            "provider_id": str(row["id"]),
            "name": row.get("name"),
            "subscriber_count": row.get("subscriber_count"),
        }
        for row in rows
        if isinstance(row, dict) and row.get("id") is not None
    ]
