from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from harbor import control_plane
from harbor.oauth import OAuthConfig
from harbor.tenant_store import TenantStore, TenantStoreError


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
        {"path": "/etc/passwd"},
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

    class VerifiedRunner:
        def verify_connection(self, sprite_name, connection_spec):
            assert sprite_name == "harbor-acme"
            assert connection_spec["provider"] == "beehiiv"
            return {
                "status": "verified",
                "provider": "beehiiv",
                "checked_at": "2026-09-06T00:00:00+00:00",
                "publication_id": "pub_example",
                "publication_name": "Example newsletter",
            }

    monkeypatch.setattr(control_plane, "SpriteRunner", VerifiedRunner)

    with pytest.raises(HTTPException) as rejected:
        control_plane.attach_connection(
            "acme",
            control_plane.ConnectionAttach(
                provider="beehiiv",
                id="bee-main",
                gateway_base_url="https://api.sprites.dev/v1/gateway/custom_api/bee-main",
                settings={"api_key": "never-store-this"},
            ),
        )
    assert rejected.value.status_code == 400

    accepted = control_plane.attach_connection(
        "acme",
        control_plane.ConnectionAttach(
            provider="beehiiv",
            id="bee-main",
            gateway_base_url="https://api.sprites.dev/v1/gateway/custom_api/bee-main",
            settings={"publication_id": "pub_example"},
        ),
    )
    assert accepted["connection"] == "bee-main"
    connection = store.get("acme").config["connections"][0]
    assert connection["settings"]["publication_id"] == "pub_example"
    assert "api_key" not in connection["settings"]
    assert connection["status"] == "verified"
    assert connection["sync"]["publication_name"] == "Example newsletter"


def test_connection_failure_is_persisted_and_visible(tmp_path, monkeypatch):
    store, _ = _tenant_store(tmp_path)
    monkeypatch.setattr(control_plane, "store", store)

    class FailedRunner:
        def verify_connection(self, sprite_name, connection_spec):
            return {
                "status": "failed",
                "provider": "beehiiv",
                "checked_at": "2026-09-06T00:00:00+00:00",
                "error": {"kind": "beehiiv_http_error", "detail": "401 unauthorized"},
            }

    monkeypatch.setattr(control_plane, "SpriteRunner", FailedRunner)
    with pytest.raises(HTTPException) as error:
        control_plane.attach_connection(
            "acme",
            control_plane.ConnectionAttach(
                provider="beehiiv",
                id="bee-main",
                gateway_base_url="https://api.sprites.dev/v1/gateway/custom_api/bee-main",
                settings={"publication_id": "pub_example"},
            ),
        )

    assert error.value.status_code == 502
    connection = store.get("acme").config["connections"][0]
    assert connection["status"] == "failed"
    assert connection["last_error"]["kind"] == "beehiiv_http_error"
    actions = {event.action for event in store.list_audit("acme")}
    assert "connection.failed" in actions


def test_connection_endpoint_rejects_non_sprite_gateway(tmp_path, monkeypatch):
    store, _ = _tenant_store(tmp_path)
    monkeypatch.setattr(control_plane, "store", store)
    with pytest.raises(HTTPException) as error:
        control_plane.attach_connection(
            "acme",
            control_plane.ConnectionAttach(
                provider="beehiiv",
                id="bee-main",
                gateway_base_url="https://attacker.example/bee-main",
                settings={"publication_id": "pub_example"},
            ),
        )
    assert error.value.status_code == 422


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


def test_tenant_can_update_schedule_and_timezone(tmp_path, monkeypatch):
    store, key = _tenant_store(tmp_path)
    monkeypatch.setattr(control_plane, "store", store)

    result = control_plane.update_worker_schedule(
        "acme",
        "newsletter-intelligence",
        control_plane.ScheduleUpdate(hour=7, minute=45, timezone="America/New_York"),
        authorization=f"Bearer {key}",
    )

    assert result["schedule"] == {"hour": 7, "minute": 45}
    assert result["timezone"] == "America/New_York"
    record = store.get("acme")
    assert record.timezone == "America/New_York"
    assert record.config["schedule"]["newsletter-intelligence"] == {
        "hour": 7,
        "minute": 45,
    }
    state = store.get_schedule_state("acme", "newsletter-intelligence")
    assert state is not None
    assert state.last_status == "scheduled"

    with pytest.raises(HTTPException) as error:
        control_plane.update_worker_schedule(
            "acme",
            "newsletter-intelligence",
            control_plane.ScheduleUpdate(hour=7, timezone="Not/A-Timezone"),
            authorization=f"Bearer {key}",
        )
    assert error.value.status_code == 400


def test_schedule_change_preserves_latest_scheduled_run_history(tmp_path, monkeypatch):
    store, key = _tenant_store(tmp_path)
    monkeypatch.setattr(control_plane, "store", store)
    window = "schedule-v1:2026-09-06:0600:UTC"
    assert store.claim_run("run_scheduled", "acme", "newsletter-intelligence", window)
    store.begin_run_attempt("run_scheduled")
    store.finish_run("run_scheduled", "completed", {"status": "completed"})

    control_plane.update_worker_schedule(
        "acme",
        "newsletter-intelligence",
        control_plane.ScheduleUpdate(hour=8, minute=15),
        authorization=f"Bearer {key}",
    )

    state = store.get_schedule_state("acme", "newsletter-intelligence")
    assert state is not None
    assert state.last_run_id == "run_scheduled"
    assert state.last_window_key == window
    assert state.last_status == "completed"
    assert state.attempt_count == 1


def test_tenant_creation_rejects_invalid_schedule_before_persisting(
    tmp_path, monkeypatch
):
    store = TenantStore(f"sqlite:///{tmp_path / 'create-tenant.db'}")
    monkeypatch.setattr(control_plane, "store", store)

    with pytest.raises(HTTPException) as error:
        control_plane.create_tenant(
            control_plane.TenantCreate(
                tenant_id="invalid",
                name="Invalid",
                timezone="Not/A-Timezone",
            )
        )

    assert error.value.status_code == 422
    with pytest.raises(TenantStoreError, match="unknown tenant"):
        store.get("invalid")


def test_tenant_can_configure_email_without_provider_credentials(tmp_path, monkeypatch):
    store, key = _tenant_store(tmp_path)
    monkeypatch.setattr(control_plane, "store", store)

    result = control_plane.update_email_output(
        "acme",
        control_plane.EmailOutputUpdate(
            recipients=["owner@example.com"], subject_prefix="Morning brief"
        ),
        authorization=f"Bearer {key}",
    )

    assert result == {"tenant_id": "acme", "enabled": True, "recipient_count": 1}
    status = control_plane.tenant_status("acme", authorization=f"Bearer {key}")
    assert status["email_output"] == {"configured": True, "recipient_count": 1}
    assert "owner@example.com" not in str(status)
    assert "email" in status["outputs"]

    with pytest.raises(ValidationError):
        control_plane.EmailOutputUpdate.model_validate(
            {"recipients": ["owner@example.com"], "api_key": "never-accepted"}
        )


def test_admin_can_issue_hashed_one_time_onboarding_invitation(tmp_path, monkeypatch):
    store = TenantStore(f"sqlite:///{tmp_path / 'invitations.db'}")
    monkeypatch.setattr(control_plane, "store", store)

    result = control_plane.create_onboarding_invitation(
        control_plane.OnboardingInvitationCreate(email="Owner@Example.com")
    )

    assert result["email"] == "owner@example.com"
    assert result["onboarding_path"] == "/onboarding"
    with store._connect() as conn:
        persisted = conn.execute(
            "SELECT code_hash FROM onboarding_invitations WHERE invitation_id=?",
            (result["invitation_id"],),
        ).fetchone()[0]
    assert persisted != result["invitation_code"]
    assert result["invitation_code"] not in persisted


def test_admin_can_configure_workspace_owner_for_oauth(tmp_path, monkeypatch):
    store, _ = _tenant_store(tmp_path)
    monkeypatch.setattr(control_plane, "store", store)

    result = control_plane.update_workspace_owner(
        "acme", control_plane.WorkspaceOwnerUpdate(email="Owner@Example.com")
    )

    assert result == {"tenant_id": "acme", "owner_configured": True}
    assert store.workspace_owner_email("acme") == "owner@example.com"


def test_oauth_protected_resource_metadata_uses_runtime_configuration(monkeypatch):
    config = OAuthConfig(
        issuer="https://auth.example.com/",
        audience="https://harbor.example.com/mcp",
        resource="https://harbor.example.com/mcp",
    )
    monkeypatch.setattr(
        control_plane, "remote_mcp", SimpleNamespace(oauth_config=config)
    )

    metadata = control_plane.oauth_protected_resource_metadata()

    assert metadata["resource"] == "https://harbor.example.com/mcp"
    assert metadata["authorization_servers"] == ["https://auth.example.com/"]
    assert metadata["scopes_supported"] == [
        "openid",
        "email",
        "harbor:read",
        "harbor:run",
    ]


def test_admin_sprite_provisioning_failure_is_persisted(tmp_path, monkeypatch):
    store = TenantStore(f"sqlite:///{tmp_path / 'provisioning-failure.db'}")
    store.create_tenant(
        "acme",
        "Acme",
        "UTC",
        {"workers": ["newsletter-intelligence"], "connections": []},
    )
    monkeypatch.setattr(control_plane, "store", store)

    class BrokenRunner:
        def provision(self, sprite_name):
            raise RuntimeError("upstream private detail")

    monkeypatch.setattr(control_plane, "SpriteRunner", BrokenRunner)
    with pytest.raises(HTTPException) as error:
        control_plane.provision_sprite("acme")

    assert error.value.status_code == 500
    assert error.value.detail == "Sprite provisioning failed"
    provisioning = store.get("acme").config["provisioning"]
    assert provisioning["status"] == "failed"
    assert provisioning["error_type"] == "RuntimeError"
    assert "upstream private detail" not in str(provisioning)


def test_readiness_and_metrics_use_durable_aggregate_state(tmp_path, monkeypatch):
    store, _ = _tenant_store(tmp_path)
    store.upsert_service_heartbeat("scheduler", "healthy", {"event_count": 0})
    monkeypatch.setattr(control_plane, "store", store)

    readiness = control_plane.readyz()
    rendered = control_plane.metrics()

    assert readiness["ok"] is True
    assert readiness["database_schema_version"] == store.schema_version
    assert "harbor_metrics_up 1" in rendered
    assert "harbor_tenants_active 1" in rendered
    assert 'harbor_scheduler_heartbeat{status="healthy"} 1' in rendered
    assert "acme" not in rendered
