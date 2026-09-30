import json
import tempfile
from pathlib import Path

from harbor import mcp_server
from harbor.config import ConfigError, load_tenant
from harbor.runtime import run_worker
from harbor.worker import catalog

assert "newsletter-intelligence" in catalog()
assert "newsletter-intelligence" in mcp_server.harbor_worker_catalog()

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    p = root / "config.json"
    p.write_text(json.dumps({
        "tenant_id": "smoke",
        "name": "Smoke Newsletter",
        "workspace": "workspace",
        "workers": ["newsletter-intelligence"],
        "connections": [{
            "id": "bee",
            "provider": "beehiiv",
            "secret_ref": "env:HARBOR_SMOKE_NO_SUCH_KEY",
            "settings": {"publication_id": "pub_smoke", "recent_posts": 3}
        }]
    }))
    t = load_tenant(p)
    result = run_worker(t, "newsletter-intelligence", {"mode": "mock"})
    assert result.status == "completed", result
    assert Path(result.deliverables[0]).exists()
    text = Path(result.deliverables[0]).read_text()
    assert "Why it matters" in text and "Recommended actions" in text

with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "bad.json"
    p.write_text(json.dumps({"tenant_id": "x", "name": "x", "api_key": "nope"}))
    try:
        load_tenant(p)
    except ConfigError:
        pass
    else:
        raise AssertionError("plaintext secret was accepted")

print("Harbor smoke tests: PASS")
