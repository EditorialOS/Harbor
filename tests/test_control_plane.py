import pytest
from fastapi import HTTPException

from harbor import control_plane
from harbor.tenant_store import TenantStore


def _tenant_store(tmp_path):
    store = TenantStore(f"sqlite:///{tmp_path / 'control-plane.db'}")
    _, key = store.create_tenant(
        "acme",
        "Acme",
        "UTC",
        {"workers": ["newsletter-intelligence"], "connections": []},
    )
    store.set_sprite("acme", "harbor-acme")
    return store, key


def test_remote_run_rejects_mock_secrets_and_reserved_fields(tmp_path, monkeypatch):
    store, key = _tenant_store(tmp_path)
    monkeypatch.setattr(control_plane, "store", store)
    authorization = f"Bearer {key}"

    for worker_input in (
        {"mode": "mock"},
        {"api_key": "never"},
        {"_harbor_run_id": "spoof"},
    ):
        with pytest.raises(HTTPException) as error:
            control_plane.run_worker_remote(
                "acme",
                "newsletter-intelligence",
                control_plane.RunRequest(input=worker_input),
                authorization=authorization,
            )
        assert error.value.status_code == 400


def test_connection_endpoint_persists_only_non_secret_metadata(tmp_path, monkeypatch):
    store, _ = _tenant_store(tmp_path)
    monkeypatch.setattr(control_plane, "store", store)
    monkeypatch.setenv("HARBOR_ADMIN_TOKEN", "local-admin-test-token")
    control_plane._admin("Bearer local-admin-test-token")

    with pytest.raises(HTTPException) as rejected:
        control_plane.attach_connection(
            "acme",
            control_plane.ConnectionAttach(
                provider="beehiiv",
                id="bee-main",
                gateway_base_url="https://connector.example.test",
                settings={"api_key": "never-store-this"},
            ),
        )
    assert rejected.value.status_code == 400

    accepted = control_plane.attach_connection(
        "acme",
        control_plane.ConnectionAttach(
            provider="beehiiv",
            id="bee-main",
            gateway_base_url="https://connector.example.test",
            settings={"publication_id": "pub_example"},
        ),
    )
    assert accepted["connection"] == "bee-main"
    connection = store.get("acme").config["connections"][0]
    assert connection["settings"]["publication_id"] == "pub_example"
    assert "api_key" not in connection["settings"]


def test_remote_run_uses_internal_identity_and_surfaces_worker_failure(
    tmp_path, monkeypatch
):
    store, key = _tenant_store(tmp_path)
    monkeypatch.setattr(control_plane, "store", store)
    captured = {}

    class FailedRunner:
        def run(self, sprite_name, run_spec):
            captured.update(run_spec)
            return {"status": "failed", "summary": "source unavailable"}

    monkeypatch.setattr(control_plane, "SpriteRunner", FailedRunner)
    with pytest.raises(HTTPException) as error:
        control_plane.run_worker_remote(
            "acme",
            "newsletter-intelligence",
            control_plane.RunRequest(input={}, idempotency_key="scheduled-window"),
            authorization=f"Bearer {key}",
        )

    assert error.value.status_code == 502
    assert captured["run_id"].startswith("run_")
    assert captured["idempotency_key_hash"] != "scheduled-window"
    assert len(captured["idempotency_key_hash"]) == 64
    with store._connect() as conn:
        row = conn.execute(
            "SELECT status FROM runs WHERE run_id=?", (captured["run_id"],)
        ).fetchone()
    assert row[0] == "failed"
