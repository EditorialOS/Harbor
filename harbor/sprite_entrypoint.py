"""Entrypoint executed *inside* a tenant Sprite.

The control plane sends non-secret run metadata. Provider auth is performed by a
Fly Sprite Connector, so no customer API key is present in the run spec or the
Sprite filesystem.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .config import ConnectionConfig, TenantConfig
from .runtime import run_worker


def tenant_from_spec(spec: dict) -> TenantConfig:
    conns = tuple(
        ConnectionConfig(
            id=c["id"],
            provider=c["provider"],
            secret_ref=None,
            settings=c.get("settings") or {},
        )
        for c in spec.get("connections", [])
    )
    return TenantConfig(
        tenant_id=spec["tenant_id"],
        name=spec["name"],
        timezone=spec.get("timezone", "UTC"),
        workspace=spec.get("workspace", "/workspace"),
        connections=conns,
        workers=tuple(spec.get("workers", [])),
        outputs=tuple(spec.get("outputs", ["files"])),
        schedule=spec.get("schedule") or {},
        context_api=spec.get("context_api"),
        gate_api=spec.get("gate_api"),
        surfaces=spec.get("surfaces") or {},
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    args = ap.parse_args()
    spec = json.loads(Path(args.spec).read_text())
    tenant = tenant_from_spec(spec)
    result = run_worker(tenant, spec["worker"], spec.get("input") or {})
    print(json.dumps(asdict(result), default=str))


if __name__ == "__main__":
    main()
