"""Harbor worker runtime — shared commercial shell around installable workers."""

from __future__ import annotations

import datetime as dt
from typing import Any

from .config import TenantConfig
from .worker import WorkerResult, get
from .workers import alex as _alex  # noqa: F401

# Import built-ins for registration.
from .workers import newsletter_intelligence as _newsletter  # noqa: F401


def run_worker(
    tenant: TenantConfig, worker_id: str, inputs: dict[str, Any] | None = None
) -> WorkerResult:
    started = dt.datetime.now(dt.timezone.utc)
    worker = get(worker_id)
    result = worker.run(tenant, inputs or {})
    result.data.setdefault("runtime", {})
    result.data["runtime"].update(
        {
            "started_at": started.isoformat(),
            "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "tenant_id": tenant.tenant_id,
            "run_id": (inputs or {}).get("_harbor_run_id"),
            "idempotency_key_hash": (inputs or {}).get("_harbor_idempotency_key_hash"),
        }
    )
    return result
