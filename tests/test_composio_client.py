import json

import httpx
import pytest

from harbor.composio_client import (
    ComposioClient,
    ComposioError,
    stable_composio_user_id,
)


def _client(handler, **kwargs):
    return ComposioClient(
        "project-secret",
        kit_auth_config_id="ac_kit",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        zdr_confirmed=True,
        callback_verification_confirmed=True,
        **kwargs,
    )


def test_connect_link_uses_stable_tenant_identity_and_no_provider_secret():
    captured = {}

    def handler(request):
        captured["request"] = request
        return httpx.Response(
            201,
            json={
                "connected_account_id": "ca_kit_one",
                "redirect_url": "https://connect.composio.dev/link/ln_safe",
            },
        )

    link = _client(handler).create_kit_link("tenant-a")

    request = captured["request"]
    body = json.loads(request.content)
    assert request.url.path == "/api/v3.1/connected_accounts/link"
    assert request.headers["x-api-key"] == "project-secret"
    assert body == {
        "auth_config_id": "ac_kit",
        "user_id": stable_composio_user_id("tenant-a"),
    }
    assert "tenant-a" not in body["user_id"]
    assert link["connected_account_id"] == "ca_kit_one"


def test_callback_completion_and_account_verification_are_tenant_bound():
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/complete_auth"):
            body = json.loads(request.content)
            assert body["session_uri"] == "session://single-use"
            assert body["user_id"] == stable_composio_user_id("tenant-a")
            return httpx.Response(
                200,
                json={"connected_account_id": "ca_kit_one", "toolkit_slug": "kit"},
            )
        return httpx.Response(
            200,
            json={
                "id": "ca_kit_one",
                "status": "ACTIVE",
                "user_id": stable_composio_user_id("tenant-a"),
                "toolkit": {"slug": "kit"},
            },
        )

    client = _client(handler)
    completed = client.complete_auth("session://single-use", "tenant-a")
    account = client.verify_kit_account(completed["connected_account_id"], "tenant-a")
    assert account["status"] == "ACTIVE"
    with pytest.raises(ComposioError, match="not active"):
        client.verify_kit_account("ca_kit_one", "tenant-b")


def test_proxy_allows_only_fixed_kit_reads_and_sanitizes_errors():
    captured = []

    def handler(request):
        captured.append(request)
        return httpx.Response(200, json={"status": 200, "data": {"account": {"id": 7}}})

    client = _client(handler)
    data = client.proxy_kit_get("ca_kit_one", "account")
    assert data["account"]["id"] == 7
    body = json.loads(captured[0].content)
    assert body["endpoint"] == "/v4/account"
    assert body["method"] == "GET"
    assert body["connected_account_id"] == "ca_kit_one"

    with pytest.raises(ComposioError, match="not allowed"):
        client.proxy_kit_get("ca_kit_one", "delete-account")
    with pytest.raises(ComposioError, match="parameter"):
        client.proxy_kit_get("ca_kit_one", "account", {"redirect": "evil"})
    assert len(captured) == 1

    secret = "provider-secret-that-must-not-escape"

    def failed(_request):
        return httpx.Response(400, json={"error": secret})

    with pytest.raises(ComposioError) as error:
        _client(failed).proxy_kit_get("ca_kit_one", "account")
    assert secret not in str(error.value)


def test_production_posture_must_be_explicitly_confirmed():
    client = ComposioClient(
        "project-secret",
        kit_auth_config_id="ac_kit",
        zdr_confirmed=False,
        callback_verification_confirmed=True,
    )
    assert not client.configured_for_kit()
    with pytest.raises(ComposioError, match="privacy"):
        client.get_connected_account("ca_kit_one")
