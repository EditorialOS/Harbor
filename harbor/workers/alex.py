"""Alex worker adapter scaffold.

This is intentionally not a pretend v3 implementation. The uploaded Alex v3
architecture says the canonical v3 worker must reconcile the live Cowork v2.4
changes into the minimal-os kernel and then call the Context API + Gate API.
Harbor v0.9 establishes that seam and preserves the supplied v2.1 kernel as
source material under workers/alex/kernel/.
"""
from __future__ import annotations

from typing import Any

from ..config import TenantConfig
from ..worker import WorkerResult, register


class AlexWorker:
    id = "alex"
    label = "Alex Content Agency"

    def run(self, tenant: TenantConfig, inputs: dict[str, Any] | None = None) -> WorkerResult:
        if not tenant.worker_enabled(self.id):
            return WorkerResult(self.id, "disabled", "Alex is not enabled for this tenant.")
        missing = []
        if not tenant.context_api:
            missing.append("context_api")
        if not tenant.gate_api:
            missing.append("gate_api")
        if missing:
            return WorkerResult(
                self.id,
                "blocked",
                "Alex adapter is installed but not runnable until the v3 services are configured.",
                warnings=["Missing tenant config: " + ", ".join(missing)],
            )
        return WorkerResult(
            self.id,
            "blocked",
            "Alex v3 reconciliation is the next build slice; v0.9 does not silently run the older v2.1 kernel as if it were v3.",
            warnings=["Requires reconciled Alex-Final + Gate API 8-criterion contract + Context API wiring."],
        )


WORKER = register(AlexWorker())
