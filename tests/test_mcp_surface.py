import contextlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

from harbor import mcp_server
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


def test_remote_mcp_auth_tools_tenant_isolation_and_idempotency(
    tmp_path, monkeypatch
):
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
                "summary": "real report completed",
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
            "harbor_worker_catalog",
            "harbor_status",
            "harbor_enabled_workers",
            "harbor_recent_runs",
            "harbor_run_worker",
        }
        assert "tenant_id" not in str(schemas)
        assert "path" not in str(schemas).lower()
        assert "input" not in schemas["harbor_run_worker"]["properties"]

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
