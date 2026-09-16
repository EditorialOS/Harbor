"""Tenant-scoped, idempotent worker dispatch shared by HTTP and scheduling."""

from __future__ import annotations

import copy
import hashlib
import os
import re
import secrets
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import quote, urlsplit

from .broker_auth import BrokerAuthError, issue_broker_grant
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
    connections = copy.deepcopy(record.config.get("connections", []))
    if worker_id == "newsletter-intelligence":
        selected_ids = inputs.get("connection_ids")
        if selected_ids is None and inputs.get("connection_id"):
            selected_ids = [inputs["connection_id"]]
        if selected_ids:
            if not isinstance(selected_ids, list) or not all(
                isinstance(item, str) and item for item in selected_ids
            ):
                raise TenantStoreError("selected newsletter sources are invalid")
            requested = set(selected_ids)
            connections = [
                item for item in connections if item.get("id") in requested
            ]
            if {item.get("id") for item in connections} != requested:
                raise TenantStoreError("selected newsletter source is not connected")
    for connection in connections:
        settings = connection.get("settings") or {}
        if connection.get("provider") != "kit" or settings.get("transport") != "composio":
            continue
        if connection.get("status") != "verified":
            raise TenantStoreError("Kit connection is not verified")
        public_url = os.environ.get("HARBOR_PUBLIC_URL")
        if not public_url and os.environ.get("FLY_APP_NAME"):
            public_url = f"https://{os.environ['FLY_APP_NAME']}.fly.dev"
        parsed = urlsplit(public_url or "")
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise TenantStoreError(
                "HARBOR_PUBLIC_URL must be an absolute HTTPS URL for Composio runs"
            )
        connection_id = str(connection.get("id") or "")
        try:
            grant = issue_broker_grant(
                tenant_id=record.tenant_id,
                connection_id=connection_id,
                provider="kit",
                run_id=run_id,
            )
        except BrokerAuthError as error:
            raise TenantStoreError(str(error)) from error
        runtime_settings = {
            key: value
            for key, value in settings.items()
            if key not in {"connected_account_id", "auth_mode", "broker_base_url", "broker_authorization"}
        }
        runtime_settings.update(
            {
                "auth_mode": "harbor_broker",
                "broker_base_url": (
                    f"{public_url.rstrip('/')}/internal/providers/kit/"
                    f"{quote(connection_id, safe='')}"
                ),
                "broker_authorization": grant,
            }
        )
        connection["settings"] = runtime_settings
    return {
        "run_id": run_id,
        "idempotency_key_hash": hashlib.sha256(idempotency_key.encode()).hexdigest(),
        "tenant_id": record.tenant_id,
        "name": record.name,
        "timezone": record.timezone,
        "workspace": "/workspace",
        "workers": record.config.get("workers", []),
        # Surface/destination configuration stays in the control plane. Workers
        # produce infrastructure-independent file artifacts inside the Sprite.
        "outputs": ["files"],
        "schedule": record.config.get("schedule", {}),
        "connections": connections,
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
    run_lease_seconds: int = 1800,
    delivery_handler: Callable[
        [TenantRecord, str, dict[str, Any]], list[dict[str, Any]]
    ]
    | None = None,
) -> tuple[str, dict[str, Any]]:
    if worker_id not in record.config.get("workers", []):
        raise TenantStoreError("worker not enabled")
    if not record.sprite_name:
        raise TenantStoreError("tenant Sprite is not provisioned")
    if max_attempts < 1 or max_attempts > 5:
        raise ValueError("max_attempts must be between 1 and 5")

    run_id = "run_" + secrets.token_hex(12)
    previous_attempts = 0
    if not store.claim_run(
        run_id,
        record.tenant_id,
        worker_id,
        idempotency_key,
        lease_seconds=run_lease_seconds,
    ):
        existing = store.get_run_by_idempotency(
            record.tenant_id, worker_id, idempotency_key
        )
        if (
            existing is None
            or existing.status != "running"
            or not store.reclaim_stale_run(
                existing.run_id, lease_seconds=run_lease_seconds
            )
        ):
            raise DuplicateRun(existing)
        run_id = existing.run_id
        previous_attempts = existing.attempt_count

    if previous_attempts >= max_attempts:
        failure = {
            "status": "failed",
            "error": {
                "kind": "worker_dispatch_failed",
                "detail": "run lease expired after the maximum attempts",
            },
            "attempts": previous_attempts,
        }
        store.finish_run(run_id, "failed", failure)
        raise RunExecutionFailed(run_id, failure)

    last_result: dict[str, Any] | None = None
    for attempt in range(previous_attempts + 1, max_attempts + 1):
        store.begin_run_attempt(run_id, lease_seconds=run_lease_seconds)
        try:
            run_spec = build_run_spec(
                record, worker_id, inputs, run_id, idempotency_key
            )
            result = runner.run(record.sprite_name, run_spec)
            validate_non_secret_metadata(result, "run.result")
            if result.get("status") == "completed" and delivery_handler is not None:
                result["deliveries"] = delivery_handler(record, run_id, result)
                validate_non_secret_metadata(result["deliveries"], "run.deliveries")
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
