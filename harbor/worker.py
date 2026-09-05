"""Worker contracts and registry."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .config import TenantConfig


@dataclass
class WorkerResult:
    worker_id: str
    status: str
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    deliverables: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class Worker(Protocol):
    id: str
    label: str

    def run(self, tenant: TenantConfig, inputs: dict[str, Any] | None = None) -> WorkerResult:
        ...


_REGISTRY: dict[str, Worker] = {}


def register(worker: Worker) -> Worker:
    _REGISTRY[worker.id] = worker
    return worker


def get(worker_id: str) -> Worker:
    try:
        return _REGISTRY[worker_id]
    except KeyError:
        raise KeyError(f"unknown worker '{worker_id}'. Known: {', '.join(sorted(_REGISTRY))}")


def catalog() -> dict[str, dict[str, str]]:
    return {
        wid: {"label": w.label, "id": wid}
        for wid, w in sorted(_REGISTRY.items())
    }
