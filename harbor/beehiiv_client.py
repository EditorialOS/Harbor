"""beehiiv API connector.

API-first. Production calls may use a Fly Sprite Connector gateway, in which
case Harbor sends no Authorization header because the connector injects the
provider credential. Direct API-key mode remains available only for local/dev.
Mock data is opt-in; production never silently substitutes fake metrics.
"""
from __future__ import annotations

import json, os, urllib.request, urllib.error, urllib.parse

BEEHIIV_BASE = os.environ.get("BEEHIIV_API_BASE", "https://api.beehiiv.com/v2")


class BeehiivError(Exception):
    def __init__(self, kind, detail):
        self.kind, self.detail = kind, detail
        super().__init__(f"{kind}: {detail}")


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
        raise BeehiivError("beehiiv_http_error", f"{e.code} {e.read()[:300]!r}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise BeehiivError("beehiiv_unreachable", str(e))


def publication_performance(
    pub_id: str,
    recent_posts: int = 5,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    auth_mode: str = "bearer",
    allow_mock: bool = False,
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

    posts = _get(
        f"/publications/{pub_id}/posts",
        {"expand[]": "stats", "limit": recent_posts, "order_by": "created", "direction": "desc"},
        api_key=api_key,
        base_url=base_url,
        auth_mode=auth_mode,
    )
    post_rows = []
    for p in posts.get("data", []):
        s = (p.get("stats", {}) or {}).get("email", {}) or {}
        w = (p.get("stats", {}) or {}).get("web", {}) or {}
        post_rows.append({
            "title": p.get("title"),
            "published": p.get("displayed_date") or p.get("created"),
            "recipients": s.get("recipients"),
            "open_rate": s.get("open_rate"),
            "click_rate": s.get("click_rate"),
            "opens": s.get("opens"),
            "clicks": s.get("clicks"),
            "web_views": w.get("views"),
        })

    return {
        "publication_id": pub_id,
        "publication_name": pdata.get("name"),
        "active_subscribers": stats.get("active_subscriptions"),
        "total_subscribers": stats.get("total_subscriptions"),
        "avg_open_rate": stats.get("average_open_rate"),
        "avg_click_rate": stats.get("average_click_rate"),
        "recent_posts": post_rows,
    }


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
