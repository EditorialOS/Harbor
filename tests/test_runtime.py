from pathlib import Path
import json

from harbor.config import ConfigError, load_tenant
from harbor.runtime import run_worker
from harbor.worker import catalog


def _tenant(tmp_path: Path) -> Path:
    p = tmp_path / "config.json"
    p.write_text(json.dumps({
        "tenant_id": "test",
        "name": "Test Newsletter",
        "workspace": "workspace",
        "workers": ["newsletter-intelligence"],
        "connections": [{
            "id": "bee",
            "provider": "beehiiv",
            "secret_ref": "env:THIS_SHOULD_NOT_EXIST_HARBOR_TEST",
            "settings": {"publication_id": "pub_test", "recent_posts": 3}
        }]
    }))
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
    assert "What matters" in text
    assert "Do next" in text
    assert "Development mode" in text


def test_plaintext_secret_is_rejected(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({
        "tenant_id": "bad",
        "name": "Bad",
        "connections": [{"provider": "beehiiv", "api_key": "secret-value"}]
    }))
    try:
        load_tenant(p)
    except ConfigError as e:
        assert "plaintext secret" in str(e)
    else:
        raise AssertionError("plaintext secret should be rejected")
