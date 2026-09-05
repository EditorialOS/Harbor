"""Local-development MCP adapter.

This module exists for local worker testing only. Production ChatGPT/Codex
integration must terminate at the Harbor Fly control plane, resolve tenant from
authenticated identity, and dispatch to that tenant's Sprite. Never expose this
file-path adapter as the public Harbor MCP service.
"""
from __future__ import annotations

import os
from dataclasses import asdict

from .config import load_tenant
from .runtime import run_worker
from .worker import catalog as _worker_catalog


def _tenant_path(path: str | None = None) -> str:
    p = path or os.environ.get("HARBOR_TENANT_CONFIG")
    if not p:
        raise RuntimeError("Set HARBOR_TENANT_CONFIG to a tenant config path.")
    return p


def harbor_worker_catalog():
    """List Harbor workers available in this runtime."""
    return _worker_catalog()


def harbor_status(tenant_config: str | None = None):
    """Return safe tenant status; never returns resolved secret values."""
    tenant = load_tenant(_tenant_path(tenant_config))
    return {
        "tenant_id": tenant.tenant_id,
        "name": tenant.name,
        "workers": list(tenant.workers),
        "connections": [c.provider for c in tenant.connections],
        "outputs": list(tenant.outputs),
        "timezone": tenant.timezone,
    }


def harbor_run_worker(worker: str, input: dict | None = None, tenant_config: str | None = None):
    """Run an enabled Harbor worker and return result + deliverable paths."""
    tenant = load_tenant(_tenant_path(tenant_config))
    return asdict(run_worker(tenant, worker, input or {}))


try:
    from mcp.server.fastmcp import FastMCP

    app = FastMCP("harbor")
    app.tool()(harbor_worker_catalog)
    app.tool()(harbor_status)
    app.tool()(harbor_run_worker)

    def serve():
        # Local stdio only. Production remote MCP belongs on the control plane.
        app.run()
except ImportError:
    app = None

    def serve():
        raise SystemExit("Install the optional `mcp` package to run Harbor as an MCP server.")
