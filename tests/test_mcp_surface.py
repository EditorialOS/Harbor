import contextlib

from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp.server.auth.provider import AccessToken

from harbor import mcp_server
from harbor.oauth import OAuthConfig
from harbor.remote_mcp import create_remote_mcp
from harbor.tenant_store import TenantStore


def _request(client, key, method, params=None):
    return client.post(
        "/mcp/",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-06-18",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
    )


def _mcp_test_app(remote):
    @contextlib.asynccontextmanager
    async def lifespan(_app):
        async with remote.server.session_manager.run():
            yield

    app = FastAPI(lifespan=lifespan)
    app.mount("/mcp", remote.app)
    return app


def test_local_mcp_tools_import_with_v2_sdk():
    catalog = mcp_server.harbor_worker_catalog()
    assert "newsletter-intelligence" in catalog
    assert mcp_server.app is not None


def test_remote_mcp_auth_tools_tenant_isolation_and_idempotency(tmp_path, monkeypatch):
    monkeypatch.setenv("HARBOR_PUBLIC_URL", "http://testserver")
    store = TenantStore(f"sqlite:///{tmp_path / 'remote-mcp.db'}")
    _, key_a = store.create_tenant(
        "acme",
        "Acme",
        "UTC",
        {
            "workers": ["newsletter-intelligence"],
            "connections": [],
            "outputs": ["files"],
        },
    )
    _, key_b = store.create_tenant(
        "beta",
        "Beta",
        "UTC",
        {"workers": [], "connections": [], "outputs": ["files"]},
    )
    store.set_sprite("acme", "harbor-acme")

    class Runner:
        calls = []

        def run(self, sprite_name, run_spec):
            self.calls.append((sprite_name, run_spec))
            return {
                "status": "completed",
                "summary": "Open performance is above recent sends.",
                "data": {
                    "metrics": {
                        "publication_name": "Acme Dispatch",
                        "active_subscribers": 1200,
                        "avg_open_rate": 0.42,
                        "avg_click_rate": 0.04,
                        "recent_posts": [
                            {
                                "id": "post_latest",
                                "title": "Latest issue",
                                "open_rate": 0.51,
                                "click_rate": 0.06,
                            }
                        ],
                    },
                    "intelligence": {
                        "headline": "Open performance is above recent sends.",
                        "what_changed": ["Open rate increased."],
                        "why_it_matters": ["More readers reached the issue."],
                        "trends": [],
                        "audience_signals": ["Active subscribers: 1,200."],
                        "recommendations": ["Reuse the subject structure."],
                        "anomalies": [],
                    },
                },
                "deliverables": ["/workspace/Work/reports/private-report.md"],
            }

    remote = create_remote_mcp(store, Runner)
    with TestClient(_mcp_test_app(remote)) as client:
        no_auth = client.post(
            "/mcp/",
            headers={"Content-Type": "application/json"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
        bad_auth = _request(client, "wrong-key", "tools/list")
        assert no_auth.status_code == 401
        assert bad_auth.status_code == 401

        listed = _request(client, key_a, "tools/list")
        assert listed.status_code == 200
        schemas = {
            tool["name"]: tool["inputSchema"]
            for tool in listed.json()["result"]["tools"]
        }
        assert set(schemas) == {
            "harbor_dashboard",
            "harbor_worker_catalog",
            "harbor_status",
            "harbor_enabled_workers",
            "harbor_recent_runs",
            "harbor_run_worker",
        }
        assert "tenant_id" not in str(schemas)
        assert "path" not in str(schemas).lower()
        assert "input" not in schemas["harbor_run_worker"]["properties"]
        tools = {
            tool["name"]: tool for tool in listed.json()["result"]["tools"]
        }
        for name in (
            "harbor_dashboard",
            "harbor_worker_catalog",
            "harbor_status",
            "harbor_enabled_workers",
            "harbor_recent_runs",
        ):
            assert tools[name]["annotations"] == {
                "readOnlyHint": True,
                "openWorldHint": False,
                "destructiveHint": False,
            }
        assert tools["harbor_run_worker"]["annotations"] == {
            "readOnlyHint": False,
            "openWorldHint": True,
            "destructiveHint": True,
            "idempotentHint": True,
        }
        assert tools["harbor_dashboard"]["_meta"]["ui"] == {
            "resourceUri": "ui://harbor/intelligence-summary-v2.html",
            "visibility": ["model", "app"],
        }

        resources = _request(client, key_a, "resources/list").json()["result"][
            "resources"
        ]
        assert resources[0]["uri"] == "ui://harbor/intelligence-summary-v2.html"
        assert resources[0]["mimeType"] == "text/html;profile=mcp-app"
        resource = _request(
            client,
            key_a,
            "resources/read",
            {"uri": "ui://harbor/intelligence-summary-v2.html"},
        ).json()["result"]["contents"][0]
        assert resource["mimeType"] == "text/html;profile=mcp-app"
        assert 'request("ui/initialize"' in resource["text"]
        assert 'notify("ui/notifications/initialized"' in resource["text"]
        assert 'protocolVersion: "2026-01-26"' in resource["text"]
        assert "ui/notifications/tool-result" in resource["text"]
        assert "Intelligence report:" in resource["text"]
        assert "What changed" in resource["text"]
        assert "Why it matters" in resource["text"]
        assert "Top action" in resource["text"]
        assert "grid-template-columns: repeat(3, 1fr)" in resource["text"]
        assert "padding: 22px 32px" in resource["text"]
        assert "<h1" not in resource["text"]
        assert "Connected" not in resource["text"]
        assert "Detailed recommendations" not in resource["text"]
        assert "<select" not in resource["text"]
        assert "class=\"tabs\"" not in resource["text"]
        assert "overflow-y" not in resource["text"]

        status_a = _request(
            client,
            key_a,
            "tools/call",
            {"name": "harbor_status", "arguments": {}},
        ).json()["result"]["structuredContent"]
        status_b = _request(
            client,
            key_b,
            "tools/call",
            {"name": "harbor_status", "arguments": {}},
        ).json()["result"]["structuredContent"]
        assert status_a["tenant_id"] == "acme"
        assert status_b["tenant_id"] == "beta"

        run_params = {
            "name": "harbor_run_worker",
            "arguments": {
                "worker_id": "newsletter-intelligence",
                "idempotency_key": "mcp-window",
            },
        }
        first = _request(client, key_a, "tools/call", run_params).json()["result"]
        second = _request(client, key_a, "tools/call", run_params).json()["result"]
        assert first["isError"] is False
        assert first["structuredContent"]["status"] == "completed"
        assert second["structuredContent"]["duplicate_suppressed"] is True
        assert len(Runner.calls) == 1
        assert "private-report.md" not in str(first) + str(second)

        dashboard = _request(
            client,
            key_a,
            "tools/call",
            {"name": "harbor_dashboard", "arguments": {}},
        ).json()["result"]["structuredContent"]
        assert dashboard["workspace"]["name"] == "Acme"
        assert dashboard["latest_intelligence"]["metrics"]["active_subscribers"] == 1200
        assert dashboard["latest_intelligence"]["intelligence"]["recommendations"] == [
            "Reuse the subject structure."
        ]
        assert "private-report.md" not in str(dashboard)

        runs_a = _request(
            client,
            key_a,
            "tools/call",
            {"name": "harbor_recent_runs", "arguments": {}},
        ).json()["result"]["structuredContent"]["runs"]
        runs_b = _request(
            client,
            key_b,
            "tools/call",
            {"name": "harbor_recent_runs", "arguments": {}},
        ).json()["result"]["structuredContent"]["runs"]
        assert len(runs_a) == 1
        assert runs_b == []
        assert "private-report.md" not in str(runs_a)


def test_remote_mcp_oauth_challenge_scopes_and_tenant_resolution(tmp_path, monkeypatch):
    monkeypatch.setenv("HARBOR_PUBLIC_URL", "http://testserver")
    store = TenantStore(f"sqlite:///{tmp_path / 'remote-oauth.db'}")
    store.create_tenant(
        "acme",
        "Acme",
        "UTC",
        {"workers": ["newsletter-intelligence"], "connections": []},
    )
    config = OAuthConfig(
        issuer="https://auth.example.com/",
        audience="http://testserver/mcp",
        resource="http://testserver/mcp",
    )

    class Verifier:
        async def verify_token(self, token):
            if token == "valid-oauth":
                return AccessToken(
                    token=token,
                    client_id="chatgpt-client",
                    scopes=list(config.required_scopes),
                    expires_at=9999999999,
                    resource=config.resource,
                    subject="auth0|owner",
                    claims={
                        "iss": config.issuer,
                        "sub": "auth0|owner",
                        "tenant_id": "acme",
                    },
                )
            if token == "missing-run-scope":
                return AccessToken(
                    token=token,
                    client_id="chatgpt-client",
                    scopes=["openid", "email", "harbor:read"],
                    expires_at=9999999999,
                    resource=config.resource,
                    subject="auth0|owner",
                    claims={"tenant_id": "acme"},
                )
            return None

    remote = create_remote_mcp(
        store,
        oauth_config=config,
        token_verifier=Verifier(),
    )
    with TestClient(_mcp_test_app(remote)) as client:
        missing = client.post("/mcp/", json={"jsonrpc": "2.0", "id": 1})
        assert missing.status_code == 401
        assert (
            f'resource_metadata="{config.metadata_url}"'
            in missing.headers["www-authenticate"]
        )

        insufficient = _request(client, "missing-run-scope", "tools/list")
        assert insufficient.status_code == 403
        assert 'error="insufficient_scope"' in insufficient.headers["www-authenticate"]

        listed = _request(client, "valid-oauth", "tools/list")
        assert listed.status_code == 200
        tools = {tool["name"]: tool for tool in listed.json()["result"]["tools"]}
        assert tools["harbor_status"]["_meta"]["securitySchemes"][0]["scopes"] == [
            "openid",
            "email",
            "harbor:read",
        ]
        assert tools["harbor_run_worker"]["_meta"]["securitySchemes"][0]["scopes"] == [
            "openid",
            "email",
            "harbor:read",
            "harbor:run",
        ]

        status = _request(
            client,
            "valid-oauth",
            "tools/call",
            {"name": "harbor_status", "arguments": {}},
        ).json()["result"]["structuredContent"]
        assert status["tenant_id"] == "acme"
