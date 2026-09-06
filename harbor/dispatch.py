"""Tenant-scoped, idempotent worker dispatch shared by HTTP and scheduling."""

from __future__ import annotations

import hashlib
import re
import secrets
import time
from collections.abc import Callable
from typing import Any

from .sprite_runner import SpriteRunner
from .tenant_store import (
    RunRecord,
    TenantRecord,
    TenantStore,
    TenantStoreError,
    validate_non_secret_metadata,
)


class DuplicateRun(RuntimeError):
    def __init__(self, record: RunRecord | None):
        self.record = record
        super().__init__("duplicate idempotency key")


class RunExecutionFailed(RuntimeError):
    def __init__(self, run_id: str, result: dict[str, Any]):
        self.run_id = run_id
        self.result = result
        super().__init__(f"worker run '{run_id}' failed")


def _safe_error(error: Exception) -> str:
    detail = f"{type(error).__name__}: {error}"
    detail = re.sub(
        r"(?i)(authorization|bearer|api[_-]?key|access[_-]?token)(\s*[:=]?\s*)\S+",
        r"\1\2[REDACTED]",
        detail,
    )
    return detail[:500]


def build_run_spec(
    record: TenantRecord,
    worker_id: str,
    inputs: dict[str, Any],
    run_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "idempotency_key_hash": hashlib.sha256(idempotency_key.encode()).hexdigest(),
        "tenant_id": record.tenant_id,
        "name": record.name,
        "timezone": record.timezone,
        "workspace": "/workspace",
        "workers": record.config.get("workers", []),
        "outputs": record.config.get("outputs", ["files"]),
        "schedule": record.config.get("schedule", {}),
        "connections": record.config.get("connections", []),
        "worker": worker_id,
        "input": inputs,
    }


def dispatch_worker(
    store: TenantStore,
    runner: SpriteRunner,
    record: TenantRecord,
    worker_id: str,
    inputs: dict[str, Any],
    idempotency_key: str,
    *,
    max_attempts: int = 1,
    retry_delay_seconds: float = 0,
    sleeper: Callable[[float], None] = time.sleep,
) -> tuple[str, dict[str, Any]]:
    if worker_id not in record.config.get("workers", []):
        raise TenantStoreError("worker not enabled")
    if not record.sprite_name:
        raise TenantStoreError("tenant Sprite is not provisioned")
    if max_attempts < 1 or max_attempts > 5:
        raise ValueError("max_attempts must be between 1 and 5")

    run_id = "run_" + secrets.token_hex(12)
    if not store.claim_run(run_id, record.tenant_id, worker_id, idempotency_key):
        raise DuplicateRun(
            store.get_run_by_idempotency(record.tenant_id, worker_id, idempotency_key)
        )

    run_spec = build_run_spec(record, worker_id, inputs, run_id, idempotency_key)
    last_result: dict[str, Any] | None = None
    for attempt in range(1, max_attempts + 1):
        store.begin_run_attempt(run_id)
        try:
            result = runner.run(record.sprite_name, run_spec)
            validate_non_secret_metadata(result, "run.result")
        except Exception as error:  # noqa: BLE001 - durable execution boundary
            # This is the execution boundary: third-party/runtime failures must
            # become durable failed attempts instead of terminating a caller.
            error_detail = _safe_error(error)
            store.record_run_attempt_error(run_id, error_detail)
            last_result = {
                "status": "failed",
                "error": {"kind": "worker_dispatch_failed", "detail": error_detail},
                "attempts": attempt,
            }
        else:
            result["attempts"] = attempt
            last_result = result
            if result.get("status") == "completed":
                store.finish_run(run_id, "completed", result)
                return run_id, result
            error_detail = str(result.get("summary") or "worker returned failed status")
            store.record_run_attempt_error(run_id, error_detail[:500])

        if attempt < max_attempts and retry_delay_seconds > 0:
            sleeper(retry_delay_seconds * (2 ** (attempt - 1)))

    failure = last_result or {
        "status": "failed",
        "error": {"kind": "worker_dispatch_failed", "detail": "unknown failure"},
        "attempts": max_attempts,
    }
    store.finish_run(run_id, "failed", failure)
    raise RunExecutionFailed(run_id, failure)
