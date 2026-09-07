"""OAuth resource-server support for Harbor's remote MCP adapter."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx
import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken

from .tenant_store import TenantRecord, TenantStore, TenantStoreError

READ_SCOPE = "harbor:read"
RUN_SCOPE = "harbor:run"
OIDC_SCOPES = ("openid", "email")
MCP_SCOPES = (*OIDC_SCOPES, READ_SCOPE, RUN_SCOPE)


def _https_url(name: str, value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError(
            f"{name} must be an HTTPS URL without credentials or query data"
        )
    return value


@dataclass(frozen=True)
class OAuthConfig:
    issuer: str
    audience: str
    resource: str
    required_scopes: tuple[str, ...] = MCP_SCOPES

    @property
    def jwks_url(self) -> str:
        return self.issuer.rstrip("/") + "/.well-known/jwks.json"

    @property
    def userinfo_url(self) -> str:
        return self.issuer.rstrip("/") + "/userinfo"

    @property
    def metadata_url(self) -> str:
        parsed = urlsplit(self.resource)
        resource_path = parsed.path if parsed.path != "/" else ""
        return (
            f"{parsed.scheme}://{parsed.netloc}/.well-known/"
            f"oauth-protected-resource{resource_path}"
        )

    def protected_resource_metadata(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "authorization_servers": [self.issuer],
            "scopes_supported": list(self.required_scopes),
            "bearer_methods_supported": ["header"],
            "resource_name": "Harbor",
        }

    @classmethod
    def from_env(cls) -> OAuthConfig | None:
        issuer = os.environ.get("HARBOR_OAUTH_ISSUER", "").strip()
        audience = os.environ.get("HARBOR_OAUTH_AUDIENCE", "").strip()
        resource = os.environ.get("HARBOR_MCP_RESOURCE", "").strip()
        required = os.environ.get("HARBOR_MCP_OAUTH_REQUIRED", "").lower() in {
            "1",
            "true",
            "yes",
        }
        supplied = [bool(issuer), bool(audience), bool(resource)]
        if any(supplied) and not all(supplied):
            raise RuntimeError(
                "HARBOR_OAUTH_ISSUER, HARBOR_OAUTH_AUDIENCE, and "
                "HARBOR_MCP_RESOURCE must be configured together"
            )
        if not all(supplied):
            if required:
                raise RuntimeError("Harbor MCP OAuth is required but is not configured")
            return None
        issuer = _https_url("HARBOR_OAUTH_ISSUER", issuer)
        audience = _https_url("HARBOR_OAUTH_AUDIENCE", audience)
        resource = _https_url("HARBOR_MCP_RESOURCE", resource)
        if audience != resource:
            raise RuntimeError(
                "HARBOR_OAUTH_AUDIENCE must exactly match HARBOR_MCP_RESOURCE"
            )
        if issuer != issuer.rstrip("/") + "/":
            raise RuntimeError(
                "HARBOR_OAUTH_ISSUER must use its exact trailing-slash issuer"
            )
        return cls(issuer=issuer, audience=audience, resource=resource)


def _token_scopes(claims: dict[str, Any]) -> list[str]:
    scopes = set()
    scope_claim = claims.get("scope")
    if isinstance(scope_claim, str):
        scopes.update(part for part in scope_claim.split() if part)
    permissions = claims.get("permissions")
    if isinstance(permissions, list):
        scopes.update(item for item in permissions if isinstance(item, str) and item)
    return sorted(scopes)


class Auth0TokenVerifier:
    """Verify Auth0 JWTs and resolve their subjects to Harbor tenants."""

    def __init__(self, store: TenantStore, config: OAuthConfig):
        self.store = store
        self.config = config
        self._keys = PyJWKClient(config.jwks_url)

    def _decode_token(self, token: str) -> dict[str, Any]:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not header.get("kid"):
            raise jwt.InvalidTokenError("unsupported token header")
        signing_key = self._keys.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=self.config.audience,
            issuer=self.config.issuer,
            leeway=30,
            options={"require": ["exp", "iat", "iss", "sub", "aud"]},
        )
        if not isinstance(claims, dict):
            raise jwt.InvalidTokenError("token claims are invalid")
        return claims

    async def _fetch_verified_email(self, token: str, subject: str) -> str:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
            response = await client.get(
                self.config.userinfo_url,
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code != 200:
            raise PermissionError("OAuth user information is unavailable")
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("sub") != subject:
            raise PermissionError("OAuth user identity does not match the token")
        if payload.get("email_verified") is not True:
            raise PermissionError("OAuth email address is not verified")
        email = payload.get("email")
        if not isinstance(email, str) or not email:
            raise PermissionError("OAuth user has no verified email address")
        return email

    async def _tenant_for_claims(
        self, token: str, claims: dict[str, Any]
    ) -> TenantRecord:
        issuer = claims.get("iss")
        subject = claims.get("sub")
        if not isinstance(issuer, str) or not isinstance(subject, str):
            raise PermissionError("OAuth identity claims are missing")
        tenant = self.store.resolve_oauth_identity(issuer, subject)
        if tenant is not None:
            return tenant
        email = await self._fetch_verified_email(token, subject)
        return self.store.bind_oauth_identity(issuer, subject, email)

    async def verify_token(self, token: str) -> AccessToken | None:
        if token.startswith("harbor_"):
            tenant = self.store.resolve_api_key(token)
            if tenant is None:
                return None
            return AccessToken(
                token=token,
                client_id="harbor-tenant-key",
                scopes=list(self.config.required_scopes),
                resource=self.config.resource,
                subject=f"tenant:{tenant.tenant_id}",
                claims={"tenant_id": tenant.tenant_id, "auth_method": "tenant_key"},
            )
        try:
            claims = await asyncio.to_thread(self._decode_token, token)
            client_id = claims.get("azp") or claims.get("client_id")
            if not isinstance(client_id, str) or not client_id:
                client_id = "oauth-client"
            scopes = _token_scopes(claims)
            common = {
                "token": token,
                "client_id": client_id,
                "scopes": scopes,
                "expires_at": int(claims["exp"]),
                "resource": self.config.resource,
                "subject": str(claims["sub"]),
            }
            if not set(self.config.required_scopes).issubset(scopes):
                return AccessToken(
                    **common,
                    claims={
                        "iss": str(claims["iss"]),
                        "sub": str(claims["sub"]),
                        "auth_method": "oauth",
                    },
                )
            tenant = await self._tenant_for_claims(token, claims)
            return AccessToken(
                **common,
                claims={
                    "iss": str(claims["iss"]),
                    "sub": str(claims["sub"]),
                    "tenant_id": tenant.tenant_id,
                    "auth_method": "oauth",
                },
            )
        except (
            httpx.HTTPError,
            jwt.PyJWTError,
            PermissionError,
            TenantStoreError,
            TypeError,
            ValueError,
        ):
            return None
