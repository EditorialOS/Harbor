import re
from typing import ClassVar

from fastapi.testclient import TestClient

from harbor import control_plane, web_portal
from harbor.outputs import AdapterReceipt
from harbor.tenant_store import TenantStore


class ProvisionedRunner:
    def provision(self, sprite_name):
        return {"sprite_name": sprite_name, "status": "ready"}


def _client(tmp_path, monkeypatch):
    store = TenantStore(f"sqlite:///{tmp_path / 'web.db'}")
    monkeypatch.setattr(control_plane, "store", store)
    monkeypatch.setattr(control_plane, "SpriteRunner", ProvisionedRunner)
    return store, TestClient(control_plane.app, base_url="https://testserver")


class CapturingEmailAdapter:
    messages: ClassVar[list] = []

    def deliver(self, message, recipients, idempotency_key):
        self.messages.append((message, recipients, idempotency_key))
        return AdapterReceipt("email-test")


def _capture_email(monkeypatch):
    CapturingEmailAdapter.messages = []
    monkeypatch.setattr(web_portal, "ResendEmailAdapter", CapturingEmailAdapter)


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
    assert "Harbor access key" not in response.text
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
    assert 'name="api_key"' in dashboard.text
    assert 'name="password"' not in dashboard.text
    assert "Workspace activity" in dashboard.text
    assert "Tenant Created" in dashboard.text


def test_customer_self_signup_emails_code_and_never_shows_access_key(
    tmp_path, monkeypatch
):
    _capture_email(monkeypatch)
    store, client = _client(tmp_path, monkeypatch)

    requested = client.post("/signup", data={"email": "new@example.com"})
    assert requested.status_code == 200
    assert "Check your email" in requested.text
    message, recipients, _ = CapturingEmailAdapter.messages[0]
    assert recipients == ["new@example.com"]
    code = re.search(r"code is: (\S+)", message.text).group(1)

    created = client.post(
        "/onboarding",
        data={
            "invitation_code": code,
            "email": "new@example.com",
            "workspace_name": "New Customer",
            "timezone": "UTC",
            "hour": "7",
            "email_delivery": "yes",
        },
    )
    assert created.status_code == 200
    assert "Your Harbor workspace is created" in created.text
    assert "access key" not in created.text.lower()
    assert store.workspace_owner_email(store.list_active()[0].tenant_id) == "new@example.com"


def test_public_legal_status_pages_and_security_headers(tmp_path, monkeypatch):
    store, client = _client(tmp_path, monkeypatch)
    store.upsert_service_heartbeat("scheduler", "healthy", {})

    privacy = client.get("/privacy")
    terms = client.get("/terms")
    support = client.get("/support")
    status = client.get("/status")

    assert privacy.status_code == 200
    assert "does not store the raw provider credential" in privacy.text
    assert terms.status_code == 200
    assert "not a final legal agreement" in terms.text
    assert support.status_code == 200
    assert "public support contact has not been configured" in support.text
    assert status.status_code == 200
    assert "Operational" in status.text
    assert "Strict-Transport-Security" in status.headers
    assert status.headers["Permissions-Policy"] == (
        "camera=(), microphone=(), geolocation=()"
    )
    policy = status.headers["Content-Security-Policy"]
    assert "form-action 'self'" in policy
    assert "https://connect.composio.dev" in policy
    assert "https://dashboard.composio.dev" in policy


def test_customer_signs_in_with_single_use_email_code(tmp_path, monkeypatch):
    _capture_email(monkeypatch)
    store, client = _client(tmp_path, monkeypatch)
    record, _ = store.create_tenant(
        "passwordless",
        "Passwordless",
        "UTC",
        {"workers": ["newsletter-intelligence"], "connections": [], "outputs": ["files"]},
    )
    store.set_workspace_owner(record.tenant_id, "owner@example.com")

    requested = client.post("/login/code", data={"email": "owner@example.com"})
    assert requested.status_code == 200
    message = CapturingEmailAdapter.messages[0][0]
    code = re.search(r"code is: (\S+)", message.text).group(1)
    signed_in = client.post(
        "/login/verify",
        data={"email": "owner@example.com", "code": code.lower()},
        follow_redirects=False,
    )
    assert signed_in.status_code == 303
    assert signed_in.headers["location"] == "/app"
    assert "harbor_session=" in signed_in.headers["set-cookie"]

    reused = client.post(
        "/login/verify",
        data={"email": "owner@example.com", "code": code},
        follow_redirects=False,
    )
    assert reused.status_code == 401


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


def test_customer_selects_kit_for_scheduled_and_manual_reports(tmp_path, monkeypatch):
    store, client = _client(tmp_path, monkeypatch)
    record, access_key = store.create_tenant(
        "source-choice",
        "Source Choice",
        "UTC",
        {
            "workers": ["newsletter-intelligence"],
            "schedule": {"newsletter-intelligence": {"hour": 6, "minute": 0}},
            "outputs": ["files"],
            "connections": [],
        },
    )
    store.set_sprite(record.tenant_id, "harbor-source-choice")
    for source_id, provider in (("bee-local", "beehiiv"), ("kit-local", "kit")):
        store.upsert_connection(
            record.tenant_id,
            {
                "id": source_id,
                "provider": provider,
                "status": "verified",
                "settings": {"publication_name": provider.title()},
            },
        )
    other, _ = store.create_tenant(
        "other-source", "Other Source", "UTC", {"workers": [], "connections": []}
    )
    store.upsert_connection(
        other.tenant_id,
        {"id": "kit-other", "provider": "kit", "status": "verified", "settings": {}},
    )

    class CapturingRunner:
        specs: ClassVar[list] = []

        def run(self, sprite_name, run_spec):
            self.specs.append(run_spec)
            return {"status": "completed", "summary": "selected source ran"}

    CapturingRunner.specs = []
    monkeypatch.setattr(control_plane, "SpriteRunner", CapturingRunner)
    client.post(
        "/login",
        data={"tenant_id": record.tenant_id, "access_key": access_key},
        follow_redirects=False,
    )
    dashboard = client.get("/app")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', dashboard.text).group(1)
    assert 'value="kit-local"' in dashboard.text
    assert 'value="kit-other"' not in dashboard.text

    rejected = client.post(
        "/app/schedule",
        data={
            "csrf_token": csrf,
            "hour": "7",
            "minute": "0",
            "timezone": "UTC",
            "connection_id": "kit-other",
        },
        follow_redirects=False,
    )
    assert rejected.headers["location"] == "/app?notice=source_invalid"

    saved = client.post(
        "/app/schedule",
        data={
            "csrf_token": csrf,
            "hour": "7",
            "minute": "0",
            "timezone": "UTC",
            "connection_id": "kit-local",
        },
        follow_redirects=False,
    )
    assert saved.headers["location"] == "/app?notice=schedule_saved"
    assert store.get(record.tenant_id).config["schedule"]["newsletter-intelligence"] == {
        "hour": 7,
        "minute": 0,
        "connection_id": "kit-local",
    }

    ran = client.post(
        "/app/run",
        data={"csrf_token": csrf, "idempotency_key": "web_source_choice_test_001"},
        follow_redirects=False,
    )
    assert ran.headers["location"] == "/app?notice=run_completed"
    assert CapturingRunner.specs[0]["input"] == {"connection_id": "kit-local"}
    assert [item["id"] for item in CapturingRunner.specs[0]["connections"]] == [
        "kit-local"
    ]


def test_web_workspace_renders_latest_intelligence_without_internal_ids(
    tmp_path, monkeypatch
):
    store, client = _client(tmp_path, monkeypatch)
    record, access_key = store.create_tenant(
        "web-report",
        "Web Report",
        "UTC",
        {
            "workers": ["newsletter-intelligence"],
            "outputs": ["files"],
            "connections": [],
        },
    )
    store.set_sprite(record.tenant_id, "harbor-web-report")
    assert store.claim_run(
        "run_web_report",
        record.tenant_id,
        "newsletter-intelligence",
        "web-report-window",
    )
    store.begin_run_attempt("run_web_report")
    store.finish_run(
        "run_web_report",
        "completed",
        {
            "status": "completed",
            "summary": "Open performance softened on the latest issue.",
            "data": {
                "metrics": {
                    "active_subscribers": 3120,
                    "avg_open_rate": 0.47,
                    "avg_click_rate": 0.032,
                    "recent_posts": [
                        {
                            "publication_id": "internal-provider-id",
                            "open_rate": 0.44,
                            "click_rate": 0.03,
                        }
                    ],
                },
                "derived": {
                    "what_changed": ["The latest issue opened below its baseline."],
                    "why_it_matters": ["The subject framing may be losing strength."],
                    "audience_signals": ["The active audience is stable."],
                    "recommendations": ["Test a clearer subject-line promise."],
                    "anomalies": ["Review <script>alert(1)</script> before acting."],
                },
            },
        },
    )

    client.post(
        "/login",
        data={"tenant_id": record.tenant_id, "access_key": access_key},
        follow_redirects=False,
    )
    dashboard = client.get("/app")

    assert dashboard.status_code == 200
    assert "Intelligence report:" in dashboard.text
    assert "3,120" in dashboard.text
    assert "44.0%" in dashboard.text
    assert "3.0%" in dashboard.text
    assert "The latest issue opened below its baseline." in dashboard.text
    assert "Test a clearer subject-line promise." in dashboard.text
    assert "Full analysis" in dashboard.text
    assert "internal-provider-id" not in dashboard.text
    assert "<script>alert(1)</script>" not in dashboard.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in dashboard.text


def test_customer_connects_kit_with_hosted_oauth_and_no_secret_form(
    tmp_path, monkeypatch
):
    store, client = _client(tmp_path, monkeypatch)
    record, access_key = store.create_tenant(
        "kit-customer",
        "Kit Customer",
        "UTC",
        {
            "workers": ["newsletter-intelligence"],
            "outputs": ["files"],
            "connections": [],
        },
    )
    store.set_sprite(record.tenant_id, "harbor-kit-customer")

    class FakeComposio:
        def configured_for_kit(self):
            return True

        def create_kit_link(self, tenant_id):
            assert tenant_id == "kit-customer"
            return {
                "connected_account_id": "ca_kit_customer",
                "redirect_url": "https://connect.composio.dev/link/ln_customer",
            }

        def complete_auth(self, session_uri, tenant_id):
            assert session_uri == "session://single-use"
            assert tenant_id == "kit-customer"
            return {"connected_account_id": "ca_kit_customer", "toolkit": "kit"}

        def verify_kit_account(self, connection_id, tenant_id):
            assert connection_id == "ca_kit_customer"
            assert tenant_id == "kit-customer"
            return {"status": "ACTIVE"}

        def proxy_kit_get(self, connection_id, operation):
            assert (connection_id, operation) == ("ca_kit_customer", "account")
            return {"account": {"id": 29, "name": "Kit Signal"}}

    monkeypatch.setattr(web_portal, "ComposioClient", FakeComposio)
    login = client.post(
        "/login",
        data={"tenant_id": record.tenant_id, "access_key": access_key},
        follow_redirects=False,
    )
    assert login.status_code == 303
    dashboard = client.get("/app")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', dashboard.text).group(1)
    assert "Connect Kit" in dashboard.text
    assert 'action="/app/connections/kit"' in dashboard.text

    started = client.post(
        "/app/connections/kit",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert started.status_code == 303
    assert started.headers["location"] == (
        "https://connect.composio.dev/link/ln_customer"
    )

    completed = client.get(
        "/app/connections/composio/verify",
        params={"session_uri": "session://single-use"},
        follow_redirects=False,
    )
    assert completed.status_code == 303
    assert completed.headers["location"] == "/app?notice=kit_ready"
    connection = store.get("kit-customer").config["connections"][0]
    assert connection["provider"] == "kit"
    assert connection["status"] == "verified"
    assert connection["settings"]["transport"] == "composio"
    assert connection["id"].startswith("kit-")
    assert connection["settings"]["connected_account_id"] == "ca_kit_customer"
    assert "credential" not in str(connection).lower()


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
        def create_beehiiv_connector(self, sprite_name, api_key):
            assert sprite_name == "harbor-connector-tenant"
            assert api_key == "temporary-beehiiv-key"
            return {
                "id": "bee-main",
                "gateway_base_url": "https://api.sprites.dev/v1/gateway/custom_api/bee-main",
            }

        def verify_connection(self, sprite_name, connection_spec):
            assert sprite_name == "harbor-connector-tenant"
            assert "api_key" not in str(connection_spec)
            settings = connection_spec["connections"][0]["settings"]
            if not settings.get("publication_id"):
                return {
                    "status": "discovered",
                    "publications": [
                        {"id": "pub_example", "name": "Example newsletter"}
                    ],
                }
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
            "api_key": "temporary-beehiiv-key",
        },
        follow_redirects=False,
    )

    assert response.headers["location"] == "/app?notice=connection_ready"
    connection = store.get(record.tenant_id).config["connections"][0]
    assert connection["status"] == "verified"
    assert connection["settings"]["publication_id"] == "pub_example"
    assert "api_key" not in str(connection)
    assert "temporary-beehiiv-key" not in str(store.list_audit(record.tenant_id))


def test_portal_lets_customer_choose_from_multiple_publications(tmp_path, monkeypatch):
    store = TenantStore(f"sqlite:///{tmp_path / 'publication-web.db'}")
    record, key = store.create_tenant(
        "publication-tenant",
        "Publication Tenant",
        "UTC",
        {
            "workers": ["newsletter-intelligence"],
            "schedule": {"newsletter-intelligence": {"hour": 6, "minute": 0}},
            "outputs": ["files"],
            "connections": [],
        },
    )
    store.set_sprite(record.tenant_id, "harbor-publication-tenant")
    monkeypatch.setattr(control_plane, "store", store)

    class MultipleRunner:
        def create_beehiiv_connector(self, sprite_name, api_key):
            return {
                "id": "bee-multiple",
                "gateway_base_url": "https://api.sprites.dev/v1/gateway/custom_api/bee-multiple",
            }

        def verify_connection(self, sprite_name, connection_spec):
            publication_id = connection_spec["connections"][0]["settings"].get(
                "publication_id"
            )
            if publication_id:
                return {
                    "status": "verified",
                    "publication_id": publication_id,
                    "publication_name": "Second newsletter",
                }
            return {
                "status": "selection_required",
                "publications": [
                    {"id": "pub_one", "name": "First newsletter"},
                    {"id": "pub_two", "name": "Second newsletter"},
                ],
            }

    monkeypatch.setattr(control_plane, "SpriteRunner", MultipleRunner)
    client = TestClient(control_plane.app, base_url="https://testserver")
    client.post(
        "/login",
        data={"tenant_id": record.tenant_id, "access_key": key},
        follow_redirects=False,
    )
    dashboard = client.get("/app")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', dashboard.text).group(1)
    connected = client.post(
        "/app/connection",
        data={"csrf_token": csrf, "api_key": "temporary-beehiiv-key"},
        follow_redirects=False,
    )
    assert connected.headers["location"] == "/app?notice=connection_select"
    chooser = client.get("/app")
    assert "First newsletter" in chooser.text
    assert "Second newsletter" in chooser.text

    selected = client.post(
        "/app/publication",
        data={"csrf_token": csrf, "publication_id": "pub_two"},
        follow_redirects=False,
    )
    assert selected.headers["location"] == "/app?notice=connection_ready"
    connection = store.get(record.tenant_id).config["connections"][0]
    assert connection["status"] == "verified"
    assert connection["settings"]["publication_id"] == "pub_two"
    assert "publications" not in connection["settings"]
