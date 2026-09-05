"""Tenant configuration for Harbor.

Harbor v0.8 keeps customer variation in tenant config and worker manifests.
Secrets are references, never values. This is the first concrete step from the
single-workspace v0.7 build toward the multi-tenant runtime described by Alex v3.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ConnectionConfig:
    id: str
    provider: str
    secret_ref: str | None = None
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TenantConfig:
    tenant_id: str
    name: str
    timezone: str = "UTC"
    workspace: str = "."
    connections: tuple[ConnectionConfig, ...] = ()
    workers: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ("files",)
    schedule: dict[str, Any] = field(default_factory=dict)
    context_api: dict[str, Any] | None = None
    gate_api: dict[str, Any] | None = None
    surfaces: dict[str, Any] = field(default_factory=dict)

    def connection(self, provider: str) -> ConnectionConfig:
        for c in self.connections:
            if c.provider == provider:
                return c
        raise ConfigError(f"tenant '{self.tenant_id}' has no '{provider}' connection")

    def worker_enabled(self, worker_id: str) -> bool:
        return worker_id in self.workers


def _reject_embedded_secrets(raw: dict[str, Any]) -> None:
    """Fail closed on likely plaintext secret fields in persisted tenant config."""
    forbidden = {"api_key", "access_token", "secret", "password", "token"}

    def walk(value: Any, path: str = ""):
        if isinstance(value, dict):
            for key, child in value.items():
                key_l = key.lower()
                child_path = f"{path}.{key}" if path else key
                if key_l in forbidden and child not in (None, "", "REDACTED"):
                    raise ConfigError(
                        f"plaintext secret-like field '{child_path}' is not allowed; "
                        "store a secret_ref such as env:BEEHIIV_API_KEY"
                    )
                walk(child, child_path)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                walk(child, f"{path}[{i}]")

    walk(raw)


def load_tenant(path: str | Path) -> TenantConfig:
    p = Path(path).resolve()
    raw = json.loads(p.read_text())
    _reject_embedded_secrets(raw)
    required = ["tenant_id", "name"]
    missing = [k for k in required if not raw.get(k)]
    if missing:
        raise ConfigError(f"missing tenant fields: {', '.join(missing)}")

    conns = tuple(
        ConnectionConfig(
            id=c.get("id") or c.get("provider", "connection"),
            provider=c["provider"],
            secret_ref=c.get("secret_ref"),
            settings=c.get("settings") or {},
        )
        for c in raw.get("connections", [])
    )

    workspace = raw.get("workspace", ".")
    # Relative workspaces are resolved relative to the config file, not process cwd.
    workspace_path = Path(workspace)
    if not workspace_path.is_absolute():
        workspace = str((p.parent / workspace_path).resolve())

    return TenantConfig(
        tenant_id=raw["tenant_id"],
        name=raw["name"],
        timezone=raw.get("timezone", "UTC"),
        workspace=workspace,
        connections=conns,
        workers=tuple(raw.get("workers", [])),
        outputs=tuple(raw.get("outputs", ["files"])),
        schedule=raw.get("schedule") or {},
        context_api=raw.get("context_api"),
        gate_api=raw.get("gate_api"),
        surfaces=raw.get("surfaces") or {},
    )
