from pathlib import Path
from harbor.tenant_store import TenantStore


def test_tenant_store_issues_and_verifies_key(tmp_path: Path):
    store = TenantStore(f"sqlite:///{tmp_path / 'harbor.db'}")
    record, key = store.create_tenant(
        "acme", "Acme", "America/Los_Angeles",
        {"workers": ["newsletter-intelligence"], "connections": []},
    )
    assert record.tenant_id == "acme"
    assert key.startswith("harbor_")
    assert store.verify_api_key("acme", key)
    assert not store.verify_api_key("acme", key + "x")


def test_run_idempotency(tmp_path: Path):
    store = TenantStore(f"sqlite:///{tmp_path / 'harbor.db'}")
    store.create_tenant("acme", "Acme", "UTC", {"workers": [], "connections": []})
    assert store.claim_run("run1", "acme", "newsletter-intelligence", "same-window")
    assert not store.claim_run("run2", "acme", "newsletter-intelligence", "same-window")
