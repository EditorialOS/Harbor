import json
from pathlib import Path

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
