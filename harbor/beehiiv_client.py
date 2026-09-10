"""beehiiv API connector.

API-first. Production calls may use a Fly Sprite Connector gateway, in which
case Harbor sends no Authorization header because the connector injects the
provider credential. Direct API-key mode remains available only for local/dev.
Mock data is opt-in; production never silently substitutes fake metrics.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BEEHIIV_BASE = os.environ.get("BEEHIIV_API_BASE", "https://api.beehiiv.com/v2")


class BeehiivError(Exception):
    def __init__(self, kind, detail):
        self.kind, self.detail = kind, detail
        super().__init__(f"{kind}: {detail}")


def _rate(value: Any) -> float | None:
    """Normalize provider rates to a 0..1 ratio.

    beehiiv's API examples contain both fractional and percentage-shaped rate
    values. Keeping this normalization at the provider boundary prevents a
    value such as ``45`` from being rendered as 4,500% in a customer report.
    """
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise BeehiivError("invalid_provider_response", "rate is not numeric") from error
    if number < 0:
        raise BeehiivError("invalid_provider_response", "rate cannot be negative")
    return number / 100 if number > 1 else number


def _get(path, params=None, *, api_key: str | None, base_url: str = BEEHIIV_BASE, auth_mode: str = "bearer"):
    url = f"{base_url.rstrip('/')}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    headers = {"Accept": "application/json"}
    if auth_mode == "bearer":
        if not api_key:
            raise BeehiivError("missing_credential", "beehiiv API key is required for direct bearer mode")
        headers["Authorization"] = f"Bearer {api_key}"
    elif auth_mode != "sprite_connector":
        raise BeehiivError("invalid_auth_mode", auth_mode)
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise BeehiivError(
            "beehiiv_http_error", f"provider returned HTTP {e.code}"
        ) from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise BeehiivError("beehiiv_unreachable", str(e))


def _timestamp(value: Any) -> dt.datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return dt.datetime.fromtimestamp(value, tz=dt.timezone.utc)
    if isinstance(value, str):
        candidate = value.strip()
        if candidate.isdigit():
            return dt.datetime.fromtimestamp(int(candidate), tz=dt.timezone.utc)
        try:
            parsed = dt.datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    return None


def _post_rows(
    pub_id: str,
    limit: int,
    *,
    api_key: str | None,
    base_url: str,
    auth_mode: str,
    start_at: dt.datetime | None,
    end_at: dt.datetime | None,
) -> list[dict[str, Any]]:
    """Fetch and locally bound Beehiiv's newest-first post pages."""
    rows: list[dict[str, Any]] = []
    page = 1
    while len(rows) < limit:
        response = _get(
            f"/publications/{pub_id}/posts",
            {
                "expand[]": "stats",
                "limit": min(100, limit - len(rows)),
                "page": page,
                "order_by": "created",
                "direction": "desc",
            },
            api_key=api_key,
            base_url=base_url,
            auth_mode=auth_mode,
        )
        current = response.get("data", [])
        if not isinstance(current, list):
            raise BeehiivError("invalid_provider_response", "posts are invalid")
        reached_start = False
        for post in current:
            if not isinstance(post, dict):
                continue
            published = _timestamp(post.get("displayed_date") or post.get("created"))
            if start_at is not None and published is not None and published < start_at:
                reached_start = True
                continue
            if end_at is not None and published is not None and published >= end_at:
                continue
            rows.append(post)
            if len(rows) >= limit:
                break
        pagination = response.get("meta") or response.get("pagination") or {}
        total_pages = pagination.get("total_pages") if isinstance(pagination, dict) else None
        if reached_start or len(rows) >= limit or not current:
            break
        if total_pages is not None and page >= int(total_pages):
            break
        if len(current) < min(100, limit - len(rows)) and total_pages is None:
            break
        page += 1
    return rows


def publication_performance(
    pub_id: str,
    recent_posts: int = 5,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    auth_mode: str = "bearer",
    allow_mock: bool = False,
    start_at: dt.datetime | None = None,
    end_at: dt.datetime | None = None,
) -> dict:
    api_key = api_key or os.environ.get("BEEHIIV_API_KEY")
    if allow_mock:
        return _mock(pub_id, recent_posts)
    base_url = base_url or BEEHIIV_BASE
    if auth_mode == "bearer" and not api_key:
        raise BeehiivError("missing_credential", "No live beehiiv credential was provided. Mock mode is explicit only.")

    pub = _get(f"/publications/{pub_id}", {"expand[]": "stats"}, api_key=api_key, base_url=base_url, auth_mode=auth_mode)
    pdata = pub.get("data", pub)
    stats = pdata.get("stats", {}) or {}

    posts = _post_rows(
        pub_id,
        recent_posts,
        api_key=api_key,
        base_url=base_url,
        auth_mode=auth_mode,
        start_at=start_at,
        end_at=end_at,
    )
    post_rows = []
    for p in posts:
        s = (p.get("stats", {}) or {}).get("email", {}) or {}
        w = (p.get("stats", {}) or {}).get("web", {}) or {}
        post_rows.append({
            "id": p.get("id"),
            "title": p.get("title"),
            "subject_line": p.get("subject_line"),
            "published": p.get("displayed_date") or p.get("created"),
            "audience": p.get("audience"),
            "content_tags": p.get("content_tags") or [],
            "recipients": s.get("recipients"),
            "delivered": s.get("delivered"),
            "open_rate": _rate(s.get("open_rate")),
            "click_rate": _rate(s.get("click_rate")),
            "opens": s.get("opens"),
            "unique_opens": s.get("unique_opens"),
            "clicks": s.get("clicks"),
            "unique_clicks": s.get("unique_clicks"),
            "unsubscribes": s.get("unsubscribes"),
            "spam_reports": s.get("spam_reports"),
            "web_views": w.get("views"),
            "web_clicks": w.get("clicks"),
            "upgrades": (p.get("stats", {}) or {}).get("upgrades"),
        })

    return {
        "publication_id": pub_id,
        "publication_name": pdata.get("name"),
        "active_subscribers": stats.get("active_subscriptions"),
        "active_free_subscribers": stats.get("active_free_subscriptions"),
        "active_premium_subscribers": stats.get("active_premium_subscriptions"),
        "total_subscribers": stats.get("total_subscriptions"),
        "total_sent": stats.get("total_sent"),
        "avg_open_rate": _rate(stats.get("average_open_rate")),
        "avg_click_rate": _rate(stats.get("average_click_rate")),
        "recent_posts": post_rows,
    }


def verify_publication(
    pub_id: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    auth_mode: str = "bearer",
) -> dict:
    """Verify read access and return only safe connection metadata."""
    api_key = api_key or os.environ.get("BEEHIIV_API_KEY")
    base_url = base_url or BEEHIIV_BASE
    if auth_mode == "bearer" and not api_key:
        raise BeehiivError(
            "missing_credential", "No live beehiiv credential was provided."
        )
    response = _get(
        f"/publications/{pub_id}",
        api_key=api_key,
        base_url=base_url,
        auth_mode=auth_mode,
    )
    publication = response.get("data", response)
    return {
        "publication_id": publication.get("id") or pub_id,
        "publication_name": publication.get("name"),
        "organization_name": publication.get("organization_name"),
    }


def list_publications(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    auth_mode: str = "bearer",
) -> list[dict[str, str | None]]:
    """Return the safe publication choices visible to a connection."""
    api_key = api_key or os.environ.get("BEEHIIV_API_KEY")
    base_url = base_url or BEEHIIV_BASE
    if auth_mode == "bearer" and not api_key:
        raise BeehiivError(
            "missing_credential", "No live beehiiv credential was provided."
        )
    response = _get(
        "/publications",
        api_key=api_key,
        base_url=base_url,
        auth_mode=auth_mode,
    )
    rows = response.get("data", [])
    if not isinstance(rows, list):
        raise BeehiivError("invalid_provider_response", "publications are invalid")
    publications = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            continue
        publications.append(
            {
                "id": row["id"],
                "name": row.get("name") if isinstance(row.get("name"), str) else None,
            }
        )
    return publications


def _mock(pub_id, n):
    return {
        "publication_id": pub_id,
        "publication_name": "Mock Newsletter",
        "active_subscribers": 3120,
        "total_subscribers": 3480,
        "avg_open_rate": 0.47,
        "avg_click_rate": 0.032,
        "recent_posts": [
            {
                "id": f"post_mock_{40-i}",
                "title": f"Issue #{40-i}",
                "published": f"2026-08-{28-i:02d}",
                "recipients": 3100,
                "open_rate": round(0.44 + 0.01 * i, 3),
                "click_rate": round(0.030 + 0.002 * i, 3),
                "opens": 1360,
                "clicks": 96,
                "web_views": 210,
            }
            for i in range(n)
        ],
        "_mock": True,
    }
