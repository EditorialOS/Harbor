"""Short-lived Harbor authorization for Sprite-to-control-plane provider calls.

The token created here is a Harbor capability, not a provider credential. It is
scoped to one tenant, connection, provider, and run, and is never persisted in
Postgres or tenant configuration.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any


class BrokerAuthError(ValueError):
    pass


@dataclass(frozen=True)
class BrokerGrant:
    tenant_id: str
    connection_id: str
    provider: str
    run_id: str
    expires_at: int


def _key(value: str | None = None) -> bytes:
    raw = value if value is not None else os.environ.get("HARBOR_BROKER_SIGNING_KEY", "")
    if len(raw.encode("utf-8")) < 32:
        raise BrokerAuthError("HARBOR_BROKER_SIGNING_KEY must contain at least 32 bytes")
    return raw.encode("utf-8")


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except Exception as error:
        raise BrokerAuthError("invalid broker authorization") from error


def issue_broker_grant(
    *,
    tenant_id: str,
    connection_id: str,
    provider: str,
    run_id: str,
    lifetime_seconds: int = 3600,
    now: int | None = None,
    signing_key: str | None = None,
) -> str:
    if lifetime_seconds < 60 or lifetime_seconds > 7200:
        raise BrokerAuthError("broker authorization lifetime is invalid")
    issued_at = int(time.time() if now is None else now)
    payload = {
        "aud": "harbor-provider-broker",
        "connection_id": connection_id,
        "exp": issued_at + lifetime_seconds,
        "iat": issued_at,
        "provider": provider,
        "run_id": run_id,
        "tenant_id": tenant_id,
        "v": 1,
    }
    encoded = _encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    signature = _encode(
        hmac.new(_key(signing_key), encoded.encode("ascii"), hashlib.sha256).digest()
    )
    return f"{encoded}.{signature}"


def verify_broker_grant(
    token: str,
    *,
    expected_connection_id: str,
    expected_provider: str,
    now: int | None = None,
    signing_key: str | None = None,
) -> BrokerGrant:
    try:
        encoded, supplied_signature = token.split(".", 1)
    except ValueError as error:
        raise BrokerAuthError("invalid broker authorization") from error
    expected_signature = _encode(
        hmac.new(_key(signing_key), encoded.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise BrokerAuthError("invalid broker authorization")
    try:
        payload: dict[str, Any] = json.loads(_decode(encoded))
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as error:
        raise BrokerAuthError("invalid broker authorization") from error
    required = {
        "aud",
        "connection_id",
        "exp",
        "iat",
        "provider",
        "run_id",
        "tenant_id",
        "v",
    }
    if set(payload) != required or payload.get("aud") != "harbor-provider-broker":
        raise BrokerAuthError("invalid broker authorization")
    timestamp = int(time.time() if now is None else now)
    try:
        expires_at = int(payload["exp"])
        issued_at = int(payload["iat"])
    except (TypeError, ValueError) as error:
        raise BrokerAuthError("invalid broker authorization") from error
    if issued_at > timestamp + 60 or expires_at <= timestamp or expires_at - issued_at > 7200:
        raise BrokerAuthError("broker authorization expired or invalid")
    if (
        payload.get("v") != 1
        or payload.get("connection_id") != expected_connection_id
        or payload.get("provider") != expected_provider
    ):
        raise BrokerAuthError("broker authorization scope is invalid")
    for field in ("tenant_id", "connection_id", "provider", "run_id"):
        if not isinstance(payload.get(field), str) or not payload[field]:
            raise BrokerAuthError("invalid broker authorization")
    return BrokerGrant(
        tenant_id=payload["tenant_id"],
        connection_id=payload["connection_id"],
        provider=payload["provider"],
        run_id=payload["run_id"],
        expires_at=expires_at,
    )
