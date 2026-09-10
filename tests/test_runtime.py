import json
from pathlib import Path

from harbor.config import ConfigError, load_tenant
from harbor.runtime import run_worker
from harbor.worker import catalog


def _tenant(tmp_path: Path) -> Path:
    p = tmp_path / "config.json"
    p.write_text(
        json.dumps(
            {
                "tenant_id": "test",
                "name": "Test Newsletter",
                "workspace": "workspace",
                "workers": ["newsletter-intelligence"],
                "connections": [
                    {
                        "id": "bee",
                        "provider": "beehiiv",
                        "secret_ref": "env:THIS_SHOULD_NOT_EXIST_HARBOR_TEST",
                        "settings": {"publication_id": "pub_test", "recent_posts": 3},
                    }
                ],
            }
        )
    )
    return p


def test_worker_catalog_has_newsletter():
    assert "newsletter-intelligence" in catalog()


def test_newsletter_worker_mock_end_to_end(tmp_path):
    tenant = load_tenant(_tenant(tmp_path))
    result = run_worker(tenant, "newsletter-intelligence", {"mode": "mock"})
    assert result.status == "completed"
    assert result.deliverables
    report = Path(result.deliverables[0])
    assert report.exists()
    text = report.read_text()
    assert "What changed" in text
    assert "Why it matters" in text
    assert "Trends vs prior performance / baseline" in text
    assert "Strongest and weakest content" in text
    assert "Audience and growth signals" in text
    assert "Recommended actions" in text
    assert "Important anomalies" in text
    assert "Development mode" in text


def test_control_plane_run_id_propagates_to_worker_artifacts(tmp_path):
    tenant = load_tenant(_tenant(tmp_path))
    result = run_worker(
        tenant,
        "newsletter-intelligence",
        {
            "mode": "mock",
            "_harbor_run_id": "run_control_plane_123",
            "_harbor_idempotency_key_hash": "digest-123",
        },
    )
    assert result.data["runtime"]["run_id"] == "run_control_plane_123"
    assert result.data["runtime"]["idempotency_key_hash"] == "digest-123"
    run_record = json.loads(Path(result.data["run_record"]).read_text())
    assert run_record["run_id"] == "run_control_plane_123"
    assert run_record["idempotency_key_hash"] == "digest-123"

    retried = run_worker(
        tenant,
        "newsletter-intelligence",
        {
            "mode": "mock",
            "_harbor_run_id": "run_control_plane_123",
            "_harbor_idempotency_key_hash": "digest-123",
        },
    )
    assert retried.deliverables == result.deliverables


def test_plaintext_secret_is_rejected(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(
        json.dumps(
            {
                "tenant_id": "bad",
                "name": "Bad",
                "connections": [{"provider": "beehiiv", "api_key": "secret-value"}],
            }
        )
    )
    try:
        load_tenant(p)
    except ConfigError as e:
        assert "plaintext secret" in str(e)
    else:
        raise AssertionError("plaintext secret should be rejected")


def test_zero_baseline_report_has_actionable_guidance(tmp_path, monkeypatch):
    tenant = load_tenant(_tenant(tmp_path))

    monkeypatch.setattr(
        "harbor.connectors.beehiiv.beehiiv_client.publication_performance",
        lambda *args, **kwargs: {
            "publication_id": "pub_test",
            "publication_name": "New publication",
            "active_subscribers": 0,
            "avg_open_rate": 0.0,
            "avg_click_rate": 0.0,
            "recent_posts": [
                {
                    "title": "First issue",
                    "recipients": 0,
                    "open_rate": 0.0,
                    "click_rate": 0.0,
                }
            ],
        },
    )

    result = run_worker(tenant, "newsletter-intelligence")
    report = Path(result.deliverables[0]).read_text()
    assert "baseline is zero or unavailable" in report
    assert "Build an initial active subscriber cohort" in report
    assert "zero email recipients" in report
    assert "Strongest recent" not in report
