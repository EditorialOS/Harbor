import re

from fastapi.testclient import TestClient

from harbor import control_plane
from harbor.tenant_store import TenantStore


class ProvisionedRunner:
    def provision(self, sprite_name):
        return {"sprite_name": sprite_name, "status": "ready"}


def _client(tmp_path, monkeypatch):
    store = TenantStore(f"sqlite:///{tmp_path / 'web.db'}")
    monkeypatch.setattr(control_plane, "store", store)
    monkeypatch.setattr(control_plane, "SpriteRunner", ProvisionedRunner)
    return store, TestClient(control_plane.app, base_url="https://testserver")


def test_invited_customer_creates_provisioned_workspace_and_session(
    tmp_path, monkeypatch
):
    store, client = _client(tmp_path, monkeypatch)
    _, invitation_code = store.create_onboarding_invitation("owner@example.com")

    response = client.post(
        "/onboarding",
        data={
            "invitation_code": invitation_code,
            "email": "owner@example.com",
            "workspace_name": "Example Newsletter",
            "timezone": "America/Los_Angeles",
            "hour": "6",
            "email_delivery": "yes",
        },
    )

    assert response.status_code == 200
    assert "Your Harbor workspace is created" in response.text
    assert "Harbor access key" in response.text
    record = store.list_active()[0]
    assert record.sprite_name is not None
    assert record.config["provisioning"]["status"] == "ready"
    assert record.config["output_settings"]["email"]["recipients"] == [
        "owner@example.com"
    ]
    assert "harbor_session=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "Secure" in response.headers["set-cookie"]

    dashboard = client.get("/app")
    assert dashboard.status_code == 200
    assert "Example Newsletter" in dashboard.text
    assert "No runs yet" in dashboard.text
    assert 'name="api_key"' not in dashboard.text
    assert 'name="password"' not in dashboard.text


def test_web_session_is_tenant_derived_and_csrf_protected(tmp_path, monkeypatch):
    store, client = _client(tmp_path, monkeypatch)
    first, first_key = store.create_tenant(
        "first",
        "First",
        "UTC",
        {
            "workers": ["newsletter-intelligence"],
            "schedule": {"newsletter-intelligence": {"hour": 6, "minute": 0}},
            "outputs": ["files"],
            "connections": [],
        },
    )
    store.create_tenant(
        "second",
        "Second",
        "UTC",
        {
            "workers": ["newsletter-intelligence"],
            "schedule": {"newsletter-intelligence": {"hour": 9, "minute": 0}},
            "outputs": ["files"],
            "connections": [],
        },
    )

    login = client.post(
        "/login",
        data={"tenant_id": first.tenant_id, "access_key": first_key},
        follow_redirects=False,
    )
    assert login.status_code == 303
    dashboard = client.get("/app")
    assert "First" in dashboard.text
    assert "Second" not in dashboard.text
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', dashboard.text).group(1)

    rejected = client.post(
        "/app/schedule",
        data={"csrf_token": "wrong", "hour": "8", "minute": "15", "timezone": "UTC"},
        follow_redirects=False,
    )
    assert rejected.headers["location"] == "/app?notice=csrf_failed"
    assert store.get("first").config["schedule"]["newsletter-intelligence"]["hour"] == 6

    saved = client.post(
        "/app/schedule",
        data={"csrf_token": csrf, "hour": "8", "minute": "15", "timezone": "UTC"},
        follow_redirects=False,
    )
    assert saved.headers["location"] == "/app?notice=schedule_saved"
    assert store.get("first").config["schedule"]["newsletter-intelligence"] == {
        "hour": 8,
        "minute": 15,
    }
    assert store.get("second").config["schedule"]["newsletter-intelligence"]["hour"] == 9


def test_failed_onboarding_provisioning_is_visible_and_persisted(
    tmp_path, monkeypatch
):
    store = TenantStore(f"sqlite:///{tmp_path / 'failed-web.db'}")
    monkeypatch.setattr(control_plane, "store", store)

    class FailedRunner:
        def provision(self, sprite_name):
            raise RuntimeError("secret-shaped upstream detail must not be persisted")

    monkeypatch.setattr(control_plane, "SpriteRunner", FailedRunner)
    client = TestClient(control_plane.app, base_url="https://testserver")
    _, invitation_code = store.create_onboarding_invitation("owner@example.com")

    response = client.post(
        "/onboarding",
        data={
            "invitation_code": invitation_code,
            "email": "owner@example.com",
            "workspace_name": "Failed Provision",
            "timezone": "UTC",
            "hour": "6",
        },
    )

    assert response.status_code == 200
    assert "Provisioning failed and was recorded" in response.text
    record = store.list_active()[0]
    assert record.sprite_name is None
    assert record.config["provisioning"] == {
        "status": "failed",
        "updated_at": record.config["provisioning"]["updated_at"],
        "error_type": "RuntimeError",
    }
    assert "secret-shaped upstream detail" not in str(record.config)


def test_portal_attaches_and_verifies_only_non_secret_connector_metadata(
    tmp_path, monkeypatch
):
    store = TenantStore(f"sqlite:///{tmp_path / 'connector-web.db'}")
    record, key = store.create_tenant(
        "connector-tenant",
        "Connector Tenant",
        "UTC",
        {
            "workers": ["newsletter-intelligence"],
            "schedule": {"newsletter-intelligence": {"hour": 6, "minute": 0}},
            "outputs": ["files"],
            "connections": [],
        },
    )
    store.set_sprite(record.tenant_id, "harbor-connector-tenant")
    monkeypatch.setattr(control_plane, "store", store)

    class VerifiedRunner:
        def verify_connection(self, sprite_name, connection_spec):
            assert sprite_name == "harbor-connector-tenant"
            assert "api_key" not in str(connection_spec)
            return {
                "status": "verified",
                "checked_at": "2026-09-06T00:00:00+00:00",
                "publication_id": "pub_example",
                "publication_name": "Example newsletter",
            }

    monkeypatch.setattr(control_plane, "SpriteRunner", VerifiedRunner)
    client = TestClient(control_plane.app, base_url="https://testserver")
    client.post(
        "/login",
        data={"tenant_id": record.tenant_id, "access_key": key},
        follow_redirects=False,
    )
    dashboard = client.get("/app")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', dashboard.text).group(1)

    response = client.post(
        "/app/connection",
        data={
            "csrf_token": csrf,
            "connection_id": "bee-main",
            "gateway_base_url": "https://api.sprites.dev/v1/gateway/custom_api/bee-main",
            "publication_id": "pub_example",
        },
        follow_redirects=False,
    )

    assert response.headers["location"] == "/app?notice=connection_ready"
    connection = store.get(record.tenant_id).config["connections"][0]
    assert connection["status"] == "verified"
    assert connection["settings"]["publication_id"] == "pub_example"
    assert "api_key" not in str(connection)
