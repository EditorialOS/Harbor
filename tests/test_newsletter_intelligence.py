import json
from pathlib import Path

from harbor import kit_client
from harbor.config import load_tenant
from harbor.runtime import run_worker


def _tenant(tmp_path: Path):
    config = tmp_path / "tenant.json"
    config.write_text(
        json.dumps(
            {
                "tenant_id": "quality-test",
                "name": "Quality Test",
                "timezone": "America/Los_Angeles",
                "workspace": "workspace",
                "workers": ["newsletter-intelligence"],
                "connections": [
                    {
                        "id": "beehiiv-test",
                        "provider": "beehiiv",
                        "settings": {
                            "auth_mode": "sprite_connector",
                            "gateway_base_url": "https://api.sprites.dev/v1/gateway/custom_api/test",
                            "publication_id": "pub_test",
                        },
                    }
                ],
            }
        )
    )
    return load_tenant(config)


def _performance(*, subscribers: int, latest_id: str, open_rate: float, click_rate: float):
    return {
        "publication_id": "pub_test",
        "publication_name": "Signal Weekly",
        "active_subscribers": subscribers,
        "active_free_subscribers": subscribers - 10,
        "active_premium_subscribers": 10,
        "total_subscribers": subscribers + 20,
        "avg_open_rate": 0.42,
        "avg_click_rate": 0.045,
        "recent_posts": [
            {
                "id": latest_id,
                "title": "A surprising new signal",
                "published": "2026-09-08T12:00:00Z",
                "recipients": 100,
                "delivered": 95,
                "open_rate": open_rate,
                "click_rate": click_rate,
                "unsubscribes": 2,
                "spam_reports": 1,
                "web_views": 80,
            },
            {
                "id": "post_prior",
                "title": "The reliable format",
                "published": "2026-09-01T12:00:00Z",
                "recipients": 100,
                "delivered": 100,
                "open_rate": 0.40,
                "click_rate": 0.05,
                "unsubscribes": 0,
                "spam_reports": 0,
                "web_views": 60,
            },
            {
                "id": "post_weak",
                "title": "The weak format",
                "published": "2026-08-25T12:00:00Z",
                "recipients": 100,
                "delivered": 100,
                "open_rate": 0.30,
                "click_rate": 0.02,
                "unsubscribes": 0,
                "spam_reports": 0,
                "web_views": 40,
            },
        ],
    }


def test_report_contains_all_paid_product_sections_and_specific_real_signals(
    tmp_path, monkeypatch
):
    tenant = _tenant(tmp_path)
    responses = iter(
        [
            _performance(
                subscribers=100,
                latest_id="post_first",
                open_rate=0.45,
                click_rate=0.04,
            ),
            _performance(
                subscribers=110,
                latest_id="post_new",
                open_rate=0.60,
                click_rate=0.09,
            ),
        ]
    )
    monkeypatch.setattr(
        "harbor.connectors.beehiiv.beehiiv_client.publication_performance",
        lambda *args, **kwargs: next(responses),
    )

    run_worker(
        tenant,
        "newsletter-intelligence",
        {"_harbor_run_id": "run_first"},
    )
    result = run_worker(
        tenant,
        "newsletter-intelligence",
        {"_harbor_run_id": "run_second"},
    )
    report = Path(result.deliverables[0]).read_text()

    for heading in (
        "What changed",
        "Why it matters",
        "Trends vs prior performance / baseline",
        "Strongest and weakest content",
        "Audience and growth signals",
        "Recommended actions",
        "Important anomalies",
    ):
        assert f"## {heading}" in report
    assert "Active subscribers: up 10 to 110" in report
    assert "Strongest opener: **A surprising new signal** at 60.0%" in report
    assert "Weakest opener: **The weak format** at 30.0%" in report
    assert "delivery was 95.0%" in report
    assert "unsubscribes were 2.0%" in report
    assert "recorded 1 spam report" in report
    assert "Source: live beehiiv data" in report

    intelligence = result.data["intelligence"]
    assert intelligence["recommendations"]
    assert intelligence["anomalies"]
    assert intelligence["trends"][0]["current"] == 0.60
    assert intelligence["best_open"]["id"] == "post_new"
    assert intelligence["weakest_open"]["id"] == "post_weak"


def test_snapshot_comparison_is_stable_when_same_run_is_retried(tmp_path, monkeypatch):
    tenant = _tenant(tmp_path)
    data = _performance(
        subscribers=100,
        latest_id="post_first",
        open_rate=0.45,
        click_rate=0.04,
    )
    monkeypatch.setattr(
        "harbor.connectors.beehiiv.beehiiv_client.publication_performance",
        lambda *args, **kwargs: data,
    )
    inputs = {
        "_harbor_run_id": "run_retry_safe",
        "_harbor_idempotency_key_hash": "safe-digest",
    }

    first = run_worker(tenant, "newsletter-intelligence", inputs)
    retried = run_worker(tenant, "newsletter-intelligence", inputs)

    assert Path(first.deliverables[0]).read_text() == Path(retried.deliverables[0]).read_text()
    assert "first saved snapshot" in Path(retried.deliverables[0]).read_text()
    state = json.loads(
        (Path(tenant.workspace) / "Work/state/newsletter-intelligence.json").read_text()
    )
    assert state["current"]["run_id"] == "run_retry_safe"
    assert state["previous"] is None
    assert "email" not in json.dumps(state).lower()


def test_explicit_timeframe_fetches_current_and_prior_period(tmp_path, monkeypatch):
    tenant = _tenant(tmp_path)
    windows = []

    def performance(*args, **kwargs):
        windows.append((kwargs["start_at"], kwargs["end_at"]))
        return _performance(
            subscribers=100,
            latest_id=f"post_{len(windows)}",
            open_rate=0.50 if len(windows) == 1 else 0.40,
            click_rate=0.06 if len(windows) == 1 else 0.04,
        )

    monkeypatch.setattr(
        "harbor.connectors.beehiiv.beehiiv_client.publication_performance",
        performance,
    )
    result = run_worker(
        tenant,
        "newsletter-intelligence",
        {"_harbor_run_id": "run_month", "timeframe": "month"},
    )

    assert result.status == "completed"
    assert len(windows) == 2
    assert windows[0][0] == windows[1][1]
    assert result.data["newsletter_data"]["window"]["label"] == "month"
    assert (
        result.data["comparison_newsletter_data"]["window"]["label"]
        == "prior_month"
    )
    assert result.data["intelligence"]["trends"][0]["baseline_label"] == "prior_month"


def test_portfolio_combines_beehiiv_and_kit_without_cross_provider_logic(
    tmp_path, monkeypatch
):
    config = tmp_path / "portfolio.json"
    config.write_text(
        json.dumps(
            {
                "tenant_id": "portfolio-test",
                "name": "Portfolio Test",
                "timezone": "UTC",
                "workspace": "workspace",
                "workers": ["newsletter-intelligence"],
                "connections": [
                    {
                        "id": "bee-main",
                        "provider": "beehiiv",
                        "settings": {
                            "auth_mode": "sprite_connector",
                            "publication_id": "pub_bee",
                        },
                    },
                    {
                        "id": "kit-main",
                        "provider": "kit",
                        "settings": {
                            "auth_mode": "sprite_connector",
                            "publication_id": "42",
                        },
                    },
                ],
            }
        )
    )
    tenant = load_tenant(config)
    monkeypatch.setattr(
        "harbor.connectors.beehiiv.beehiiv_client.publication_performance",
        lambda *args, **kwargs: {
            **_performance(
                subscribers=120,
                latest_id="bee_issue",
                open_rate=0.52,
                click_rate=0.06,
            ),
            "publication_id": "pub_bee",
            "publication_name": "Brand Daily",
        },
    )

    def kit_get(path, params=None, **kwargs):
        if path == "/account":
            return {"account": {"id": 42, "name": "Executive Brief", "timezone": {}}}
        if path == "/subscribers":
            return {"subscribers": [], "pagination": {"total_count": 80}}
        if path == "/account/growth_stats":
            return {"stats": {"net_new_subscribers": 4}}
        if path == "/tags":
            return {"tags": [], "pagination": {"has_next_page": False}}
        if path == "/broadcasts/stats":
            return {
                "broadcasts": [
                    {
                        "id": 700,
                        "subject": "Executive signal",
                        "send_at": "2026-09-09T12:00:00Z",
                        "stats": {
                            "recipients": 80,
                            "open_rate": 40,
                            "click_rate": 3,
                            "emails_opened": 32,
                            "total_clicks": 2,
                            "unsubscribes": 0,
                            "unsubscribe_rate": 0,
                        },
                    }
                ],
                "pagination": {"total_count": 1, "has_next_page": False},
            }
        raise AssertionError(path)

    monkeypatch.setattr(kit_client, "_get", kit_get)
    result = run_worker(
        tenant,
        "newsletter-intelligence",
        {
            "_harbor_run_id": "run_portfolio",
            "view": "portfolio",
            "timeframe": "last_7_days",
        },
    )

    assert result.status == "completed"
    assert len(result.data["newsletter_data"]["publications"]) == 2
    assert result.data["metrics"]["active_subscribers"] == 200
    assert result.data["metrics"]["publication_count"] == 2
    assert result.data["intelligence"]["strongest_publication"]["publication_name"] == "Brand Daily"
    report = Path(result.deliverables[0]).read_text()
    assert "## Publication comparison" in report
    assert "Brand Daily" in report
    assert "Executive Brief" in report
    assert "live portfolio data retrieved for 2 selected publications" in report
