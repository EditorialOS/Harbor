import asyncio
import datetime as dt

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from harbor.oauth import Auth0TokenVerifier, OAuthConfig
from harbor.tenant_store import TenantStore


def _tenant_with_owner(store: TenantStore, tenant_id: str, email: str):
    store.create_tenant(
        tenant_id,
        tenant_id.title(),
        "UTC",
        {"workers": ["newsletter-intelligence"], "connections": []},
    )
    store.set_workspace_owner(tenant_id, email)


def test_oauth_config_requires_complete_exact_https_values(monkeypatch):
    for name in (
        "HARBOR_OAUTH_ISSUER",
        "HARBOR_OAUTH_AUDIENCE",
        "HARBOR_MCP_RESOURCE",
        "HARBOR_MCP_OAUTH_REQUIRED",
    ):
        monkeypatch.delenv(name, raising=False)
    assert OAuthConfig.from_env() is None

    monkeypatch.setenv("HARBOR_MCP_OAUTH_REQUIRED", "1")
    with pytest.raises(RuntimeError, match="required"):
        OAuthConfig.from_env()

    monkeypatch.setenv("HARBOR_OAUTH_ISSUER", "https://auth.example.com/")
    monkeypatch.setenv("HARBOR_OAUTH_AUDIENCE", "https://harbor.example.com/mcp")
    monkeypatch.setenv("HARBOR_MCP_RESOURCE", "https://harbor.example.com/mcp")
    config = OAuthConfig.from_env()
    assert config is not None
    assert config.metadata_url == (
        "https://harbor.example.com/.well-known/oauth-protected-resource/mcp"
    )
    assert config.protected_resource_metadata()["authorization_servers"] == [
        "https://auth.example.com/"
    ]


def test_auth0_verifier_checks_signature_claims_and_binds_verified_owner(
    tmp_path, monkeypatch
):
    store = TenantStore(f"sqlite:///{tmp_path / 'oauth-verifier.db'}")
    _tenant_with_owner(store, "acme", "owner@example.com")
    config = OAuthConfig(
        issuer="https://auth.example.com/",
        audience="https://harbor.example.com/mcp",
        resource="https://harbor.example.com/mcp",
    )
    verifier = Auth0TokenVerifier(store, config)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class SigningKey:
        key = private_key.public_key()

    monkeypatch.setattr(
        verifier._keys, "get_signing_key_from_jwt", lambda _token: SigningKey()
    )

    async def verified_email(_token, _subject):
        return "owner@example.com"

    monkeypatch.setattr(verifier, "_fetch_verified_email", verified_email)
    now = dt.datetime.now(dt.timezone.utc)
    claims = {
        "iss": config.issuer,
        "sub": "auth0|owner",
        "aud": config.audience,
        "azp": "chatgpt-client",
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(minutes=5)).timestamp()),
        "scope": "openid email harbor:read harbor:run",
    }
    token = jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "one"})
    access = asyncio.run(verifier.verify_token(token))

    assert access is not None
    assert access.subject == "auth0|owner"
    assert access.resource == config.resource
    assert access.claims == {
        "iss": config.issuer,
        "sub": "auth0|owner",
        "tenant_id": "acme",
        "auth_method": "oauth",
    }
    assert set(access.scopes) == {"openid", "email", "harbor:read", "harbor:run"}

    wrong_audience = jwt.encode(
        {**claims, "aud": "https://other.example.com"},
        private_key,
        algorithm="RS256",
        headers={"kid": "one"},
    )
    assert asyncio.run(verifier.verify_token(wrong_audience)) is None

    expired = jwt.encode(
        {
            **claims,
            "iat": int((now - dt.timedelta(hours=2)).timestamp()),
            "exp": int((now - dt.timedelta(hours=1)).timestamp()),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "one"},
    )
    assert asyncio.run(verifier.verify_token(expired)) is None


def test_auth0_verifier_rejects_unverified_or_unknown_owner(tmp_path, monkeypatch):
    store = TenantStore(f"sqlite:///{tmp_path / 'oauth-no-owner.db'}")
    _tenant_with_owner(store, "acme", "owner@example.com")
    config = OAuthConfig(
        issuer="https://auth.example.com/",
        audience="https://harbor.example.com/mcp",
        resource="https://harbor.example.com/mcp",
    )
    verifier = Auth0TokenVerifier(store, config)
    claims = {
        "iss": config.issuer,
        "sub": "auth0|unknown",
        "aud": config.audience,
        "iat": 1,
        "exp": 9999999999,
        "scope": "openid email harbor:read harbor:run",
    }
    monkeypatch.setattr(verifier, "_decode_token", lambda _token: claims)

    calls = []

    async def should_not_fetch(_token, _subject):
        calls.append(True)
        return "owner@example.com"

    monkeypatch.setattr(verifier, "_fetch_verified_email", should_not_fetch)
    claims["scope"] = "openid email harbor:read"
    insufficient = asyncio.run(verifier.verify_token("jwt-value"))
    assert insufficient is not None
    assert "tenant_id" not in insufficient.claims
    assert calls == []

    claims["scope"] = "openid email harbor:read harbor:run"

    async def unknown_email(_token, _subject):
        return "unknown@example.com"

    monkeypatch.setattr(verifier, "_fetch_verified_email", unknown_email)
    assert asyncio.run(verifier.verify_token("jwt-value")) is None

    async def unverified(_token, _subject):
        raise PermissionError("OAuth email address is not verified")

    monkeypatch.setattr(verifier, "_fetch_verified_email", unverified)
    assert asyncio.run(verifier.verify_token("jwt-value")) is None
