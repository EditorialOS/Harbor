"""Postgres-backed scheduler process for Harbor tenant workers."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import time
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .billing import billing_is_active
from .dispatch import DuplicateRun, RunExecutionFailed, dispatch_worker
from .outputs import DeliveryCoordinator
from .sprite_runner import SpriteRunner
from .tenant_store import TenantRecord, TenantStore, TenantStoreError


@dataclass(frozen=True)
class DailySchedule:
    hour: int
    minute: int


def parse_daily_schedule(value: Any) -> DailySchedule:
    if not isinstance(value, dict):
        raise TypeError("schedule must be an object")
    hour = value.get("hour")
    minute = value.get("minute", 0)
    if isinstance(hour, bool) or not isinstance(hour, int) or hour < 0 or hour > 23:
        raise ValueError("schedule hour must be an integer from 0 through 23")
    if (
        isinstance(minute, bool)
        or not isinstance(minute, int)
        or minute < 0
        or minute > 59
    ):
        raise ValueError("schedule minute must be an integer from 0 through 59")
    return DailySchedule(hour, minute)


def next_occurrence(
    now: dt.datetime, timezone: str, schedule: DailySchedule
) -> dt.datetime:
    if now.tzinfo is None:
        raise ValueError("scheduler time must be timezone-aware")
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"unknown tenant timezone '{timezone}'") from error
    local_now = now.astimezone(zone)
    candidate = dt.datetime.combine(
        local_now.date(),
        dt.time(schedule.hour, schedule.minute),
        tzinfo=zone,
    )
    if candidate <= local_now:
        candidate += dt.timedelta(days=1)
    return candidate.astimezone(dt.timezone.utc)


def window_key(due_at: dt.datetime, timezone: str, schedule: DailySchedule) -> str:
    local_due = due_at.astimezone(ZoneInfo(timezone))
    return (
        f"schedule-v1:{local_due.date().isoformat()}:"
        f"{schedule.hour:02d}{schedule.minute:02d}:{timezone}"
    )


class Scheduler:
    def __init__(
        self,
        store: TenantStore,
        runner: SpriteRunner,
        *,
        max_attempts: int = 3,
        retry_delay_seconds: float = 2,
        sleeper=time.sleep,
        delivery_handler=None,
        run_lease_seconds: int = 1800,
    ):
        self.store = store
        self.runner = runner
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.sleeper = sleeper
        self.delivery_handler = delivery_handler
        self.run_lease_seconds = run_lease_seconds

    def _initialize(
        self,
        tenant: TenantRecord,
        worker_id: str,
        schedule: DailySchedule,
        now: dt.datetime,
    ) -> dict[str, Any]:
        next_at = next_occurrence(now, tenant.timezone, schedule)
        self.store.upsert_schedule_state(
            tenant.tenant_id,
            worker_id,
            next_run_at=next_at.isoformat(),
            last_status="scheduled",
        )
        return {
            "tenant_id": tenant.tenant_id,
            "worker_id": worker_id,
            "status": "scheduled",
            "next_run_at": next_at.isoformat(),
        }

    def tick(self, now: dt.datetime | None = None) -> list[dict[str, Any]]:
        now = now or dt.datetime.now(dt.timezone.utc)
        if now.tzinfo is None:
            raise ValueError("scheduler time must be timezone-aware")
        now = now.astimezone(dt.timezone.utc)
        events: list[dict[str, Any]] = []
        for tenant in self.store.list_active():
            if tenant.config.get("billing_required") and not billing_is_active(
                self.store.get_billing(tenant.tenant_id)
            ):
                continue
            schedules = tenant.config.get("schedule", {})
            for worker_id, raw_schedule in schedules.items():
                if worker_id not in tenant.config.get("workers", []):
                    continue
                state = self.store.get_schedule_state(tenant.tenant_id, worker_id)
                try:
                    schedule = parse_daily_schedule(raw_schedule)
                    ZoneInfo(tenant.timezone)
                except (TypeError, ValueError, ZoneInfoNotFoundError) as error:
                    if state is not None:
                        configured_retry = dt.datetime.fromisoformat(state.next_run_at)
                        if configured_retry.tzinfo is None:
                            configured_retry = configured_retry.replace(
                                tzinfo=dt.timezone.utc
                            )
                        if now < configured_retry.astimezone(dt.timezone.utc):
                            continue
                    retry_at = now + dt.timedelta(hours=1)
                    self.store.upsert_schedule_state(
                        tenant.tenant_id,
                        worker_id,
                        next_run_at=retry_at.isoformat(),
                        last_status="configuration_failed",
                        last_error=str(error)[:500],
                    )
                    events.append(
                        {
                            "tenant_id": tenant.tenant_id,
                            "worker_id": worker_id,
                            "status": "configuration_failed",
                            "error": str(error),
                        }
                    )
                    continue

                if state is None:
                    events.append(self._initialize(tenant, worker_id, schedule, now))
                    continue
                due_at = dt.datetime.fromisoformat(state.next_run_at)
                if due_at.tzinfo is None:
                    due_at = due_at.replace(tzinfo=dt.timezone.utc)
                due_at = due_at.astimezone(dt.timezone.utc)
                if now < due_at:
                    continue

                key = window_key(due_at, tenant.timezone, schedule)
                # Skip stale backlog windows after downtime; execute at most one
                # overdue window, then schedule the next future occurrence.
                next_at = next_occurrence(now, tenant.timezone, schedule)
                try:
                    run_id, result = dispatch_worker(
                        self.store,
                        self.runner,
                        tenant,
                        worker_id,
                        {},
                        key,
                        max_attempts=self.max_attempts,
                        retry_delay_seconds=self.retry_delay_seconds,
                        sleeper=self.sleeper,
                        delivery_handler=self.delivery_handler,
                        run_lease_seconds=self.run_lease_seconds,
                    )
                except DuplicateRun as error:
                    run = error.record
                    status = run.status if run else "duplicate"
                    self.store.upsert_schedule_state(
                        tenant.tenant_id,
                        worker_id,
                        next_run_at=next_at.isoformat(),
                        last_window_key=key,
                        last_run_id=run.run_id if run else None,
                        last_status=status,
                        attempt_count=run.attempt_count if run else 0,
                        last_error=run.last_error if run else None,
                    )
                    events.append(
                        {
                            "tenant_id": tenant.tenant_id,
                            "worker_id": worker_id,
                            "status": "duplicate_suppressed",
                            "run_id": run.run_id if run else None,
                        }
                    )
                except RunExecutionFailed as error:
                    attempts = int(error.result.get("attempts", self.max_attempts))
                    detail = (error.result.get("error") or {}).get("detail")
                    self.store.upsert_schedule_state(
                        tenant.tenant_id,
                        worker_id,
                        next_run_at=next_at.isoformat(),
                        last_window_key=key,
                        last_run_id=error.run_id,
                        last_status="failed",
                        attempt_count=attempts,
                        last_error=detail,
                    )
                    events.append(
                        {
                            "tenant_id": tenant.tenant_id,
                            "worker_id": worker_id,
                            "status": "failed",
                            "run_id": error.run_id,
                            "attempts": attempts,
                        }
                    )
                except TenantStoreError as error:
                    detail = str(error)[:500]
                    self.store.upsert_schedule_state(
                        tenant.tenant_id,
                        worker_id,
                        next_run_at=next_at.isoformat(),
                        last_window_key=key,
                        last_status="failed",
                        last_error=detail,
                    )
                    events.append(
                        {
                            "tenant_id": tenant.tenant_id,
                            "worker_id": worker_id,
                            "status": "failed",
                            "run_id": None,
                            "attempts": 0,
                        }
                    )
                else:
                    attempts = int(result.get("attempts", 1))
                    self.store.upsert_schedule_state(
                        tenant.tenant_id,
                        worker_id,
                        next_run_at=next_at.isoformat(),
                        last_window_key=key,
                        last_run_id=run_id,
                        last_status="completed",
                        attempt_count=attempts,
                    )
                    events.append(
                        {
                            "tenant_id": tenant.tenant_id,
                            "worker_id": worker_id,
                            "status": "completed",
                            "run_id": run_id,
                            "attempts": attempts,
                        }
                    )
        return events


def monitored_tick(scheduler: Scheduler, store: TenantStore) -> list[dict[str, Any]]:
    store.upsert_service_heartbeat("scheduler", "running", {"phase": "tick"})
    try:
        events = scheduler.tick()
    except Exception as error:
        try:
            store.upsert_service_heartbeat(
                "scheduler",
                "failed",
                {"error_type": type(error).__name__},
            )
        finally:
            raise
    store.upsert_service_heartbeat(
        "scheduler",
        "healthy",
        {"event_count": len(events)},
    )
    return events


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    poll_seconds = max(10, int(os.environ.get("HARBOR_SCHEDULER_POLL_SECONDS", "30")))
    max_attempts = int(os.environ.get("HARBOR_SCHEDULER_MAX_ATTEMPTS", "3"))
    retry_delay = float(os.environ.get("HARBOR_SCHEDULER_RETRY_DELAY_SECONDS", "2"))
    run_lease_seconds = int(os.environ.get("HARBOR_RUN_LEASE_SECONDS", "1800"))
    store = TenantStore()
    runner = SpriteRunner()
    scheduler = Scheduler(
        store,
        runner,
        max_attempts=max_attempts,
        retry_delay_seconds=retry_delay,
        delivery_handler=DeliveryCoordinator(store, runner).deliver,
        run_lease_seconds=run_lease_seconds,
    )
    while True:
        for event in monitored_tick(scheduler, store):
            print(json.dumps(event), flush=True)
        if args.once:
            return
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
