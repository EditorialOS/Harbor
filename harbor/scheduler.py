"""Postgres-backed scheduler process for Harbor tenant workers."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import time
from dataclasses import dataclass, replace
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .billing import billing_is_active
from .dispatch import DuplicateRun, RunExecutionFailed, dispatch_worker
from .outputs import DeliveryCoordinator, DeliveryError, validate_email_recipient
from .sprite_runner import SpriteRunner
from .tenant_store import (
    TenantRecord,
    TenantStore,
    TenantStoreError,
    validate_non_secret_metadata,
)


@dataclass(frozen=True)
class DailySchedule:
    hour: int
    minute: int


@dataclass(frozen=True)
class ReportSchedule:
    frequency: str
    hour: int
    minute: int
    weekday: int | None = None
    day: int | None = None
    weekdays: tuple[int, ...] = ()
    first_weekday: bool = False


@dataclass(frozen=True)
class ScheduledJob:
    schedule_id: str
    state_id: str
    worker_id: str
    schedule: ReportSchedule
    inputs: dict[str, Any]
    output_settings: dict[str, Any] | None = None


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


_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _weekday(value: Any) -> int:
    if isinstance(value, str):
        try:
            return _WEEKDAYS[value.strip().lower()]
        except KeyError as error:
            raise ValueError("schedule weekday must be Monday through Sunday") from error
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 6:
        raise ValueError("schedule weekday must be an integer from 0 through 6")
    return value


def parse_report_schedule(value: Any) -> ReportSchedule:
    daily = parse_daily_schedule(value)
    frequency = str(value.get("frequency", "daily")).strip().lower()
    if frequency not in {"daily", "weekly", "monthly", "quarterly", "custom"}:
        raise ValueError(
            "schedule frequency must be daily, weekly, monthly, quarterly, or custom"
        )
    weekday = _weekday(value.get("weekday", 0)) if frequency == "weekly" else None
    first_weekday = bool(value.get("first_weekday", False))
    day = value.get("day")
    if frequency in {"monthly", "quarterly"} and not first_weekday:
        day = 1 if day is None else day
        if isinstance(day, bool) or not isinstance(day, int) or not 1 <= day <= 28:
            raise ValueError("monthly schedule day must be an integer from 1 through 28")
    else:
        day = None
    weekdays: tuple[int, ...] = ()
    if frequency == "custom":
        raw_weekdays = value.get("weekdays")
        if not isinstance(raw_weekdays, list) or not raw_weekdays:
            raise ValueError("custom schedule requires at least one weekday")
        weekdays = tuple(sorted({_weekday(item) for item in raw_weekdays}))
    return ReportSchedule(
        frequency=frequency,
        hour=daily.hour,
        minute=daily.minute,
        weekday=weekday,
        day=day,
        weekdays=weekdays,
        first_weekday=first_weekday,
    )


def _is_first_weekday(value: dt.date) -> bool:
    return value.weekday() < 5 and not any(
        (value - dt.timedelta(days=offset)).month == value.month
        and (value - dt.timedelta(days=offset)).weekday() < 5
        for offset in range(1, value.day)
    )


def _date_matches(value: dt.date, schedule: ReportSchedule) -> bool:
    if schedule.frequency == "daily":
        return True
    if schedule.frequency == "weekly":
        return value.weekday() == schedule.weekday
    if schedule.frequency == "custom":
        return value.weekday() in schedule.weekdays
    if schedule.frequency == "quarterly" and value.month not in {1, 4, 7, 10}:
        return False
    if schedule.first_weekday:
        return _is_first_weekday(value)
    return value.day == schedule.day


def next_report_occurrence(
    now: dt.datetime, timezone: str, schedule: ReportSchedule
) -> dt.datetime:
    if now.tzinfo is None:
        raise ValueError("scheduler time must be timezone-aware")
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"unknown tenant timezone '{timezone}'") from error
    local_now = now.astimezone(zone)
    for offset in range(380):
        day = local_now.date() + dt.timedelta(days=offset)
        if not _date_matches(day, schedule):
            continue
        candidate = dt.datetime.combine(
            day, dt.time(schedule.hour, schedule.minute), tzinfo=zone
        )
        if candidate > local_now:
            return candidate.astimezone(dt.timezone.utc)
    raise ValueError("schedule has no occurrence in the supported planning horizon")


def report_window_key(
    due_at: dt.datetime,
    timezone: str,
    schedule_id: str,
    schedule: ReportSchedule,
) -> str:
    local_due = due_at.astimezone(ZoneInfo(timezone))
    return (
        f"report-schedule-v1:{schedule_id}:{local_due.date().isoformat()}:"
        f"{schedule.hour:02d}{schedule.minute:02d}:{timezone}"
    )


def configured_jobs(tenant: TenantRecord) -> list[ScheduledJob]:
    raw_reports = tenant.config.get("report_schedules") or []
    if not isinstance(raw_reports, list):
        raise TypeError("report_schedules must be a list")
    jobs: list[ScheduledJob] = []
    modern_workers: set[str] = set()
    seen_ids: set[str] = set()
    for raw in raw_reports:
        if not isinstance(raw, dict):
            raise TypeError("each report schedule must be an object")
        if raw.get("enabled", True) is False:
            continue
        schedule_id = str(raw.get("id") or "")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", schedule_id):
            raise ValueError("report schedule id is invalid")
        if schedule_id in seen_ids:
            raise ValueError(f"duplicate report schedule id '{schedule_id}'")
        seen_ids.add(schedule_id)
        worker_id = str(raw.get("worker_id") or "newsletter-intelligence")
        if worker_id not in tenant.config.get("workers", []):
            raise ValueError(f"report schedule worker '{worker_id}' is not enabled")
        inputs = raw.get("input") or {}
        if not isinstance(inputs, dict):
            raise TypeError("report schedule input must be an object")
        validate_non_secret_metadata(inputs, "report_schedule.input")
        output_settings = raw.get("output_settings")
        if output_settings is not None:
            if not isinstance(output_settings, dict):
                raise TypeError("report output_settings must be an object")
            validate_non_secret_metadata(
                output_settings, "report_schedule.output_settings"
            )
            email = output_settings.get("email")
            if email is not None:
                if not isinstance(email, dict):
                    raise TypeError("report email settings must be an object")
                recipients = email.get("recipients") or []
                if not isinstance(recipients, list) or not 1 <= len(recipients) <= 50:
                    raise ValueError("report email requires 1 through 50 recipients")
                try:
                    for recipient in recipients:
                        validate_email_recipient(str(recipient))
                except DeliveryError as error:
                    raise ValueError(str(error)) from error
        jobs.append(
            ScheduledJob(
                schedule_id=schedule_id,
                state_id=f"report:{schedule_id}",
                worker_id=worker_id,
                schedule=parse_report_schedule(raw.get("schedule")),
                inputs=dict(inputs),
                output_settings=(
                    dict(output_settings) if output_settings is not None else None
                ),
            )
        )
        modern_workers.add(worker_id)

    legacy = tenant.config.get("schedule") or {}
    if not isinstance(legacy, dict):
        raise TypeError("schedule must be an object")
    for worker_id, raw_schedule in legacy.items():
        if worker_id in modern_workers or worker_id not in tenant.config.get("workers", []):
            continue
        jobs.append(
            ScheduledJob(
                schedule_id=worker_id,
                state_id=worker_id,
                worker_id=worker_id,
                schedule=parse_report_schedule(raw_schedule),
                inputs={},
            )
        )
    return jobs


def _configuration_identity(tenant: TenantRecord) -> tuple[str, str, str | None]:
    reports = tenant.config.get("report_schedules") or []
    if isinstance(reports, list) and reports and isinstance(reports[0], dict):
        schedule_id = str(reports[0].get("id") or "configuration")
        worker_id = str(
            reports[0].get("worker_id") or "newsletter-intelligence"
        )
        return f"report:{schedule_id}", worker_id, schedule_id
    legacy = tenant.config.get("schedule") or {}
    worker_id = (
        str(next(iter(legacy)))
        if isinstance(legacy, dict) and legacy
        else "newsletter-intelligence"
    )
    return worker_id, worker_id, worker_id


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
        job: ScheduledJob,
        now: dt.datetime,
    ) -> dict[str, Any]:
        next_at = next_report_occurrence(now, tenant.timezone, job.schedule)
        self.store.upsert_schedule_state(
            tenant.tenant_id,
            job.state_id,
            next_run_at=next_at.isoformat(),
            last_status="scheduled",
        )
        return {
            "tenant_id": tenant.tenant_id,
            "worker_id": job.worker_id,
            "schedule_id": job.schedule_id,
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
            try:
                jobs = configured_jobs(tenant)
            except (TypeError, ValueError, TenantStoreError) as error:
                state_id, worker_id, schedule_id = _configuration_identity(tenant)
                state = self.store.get_schedule_state(tenant.tenant_id, state_id)
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
                    state_id,
                    next_run_at=retry_at.isoformat(),
                    last_status="configuration_failed",
                    last_error=str(error)[:500],
                )
                events.append(
                    {
                        "tenant_id": tenant.tenant_id,
                        "worker_id": worker_id,
                        "schedule_id": schedule_id,
                        "status": "configuration_failed",
                        "error": str(error),
                    }
                )
                continue
            for job in jobs:
                state = self.store.get_schedule_state(tenant.tenant_id, job.state_id)

                if state is None:
                    events.append(self._initialize(tenant, job, now))
                    continue
                due_at = dt.datetime.fromisoformat(state.next_run_at)
                if due_at.tzinfo is None:
                    due_at = due_at.replace(tzinfo=dt.timezone.utc)
                due_at = due_at.astimezone(dt.timezone.utc)
                if now < due_at:
                    continue

                key = (
                    window_key(
                        due_at,
                        tenant.timezone,
                        DailySchedule(job.schedule.hour, job.schedule.minute),
                    )
                    if job.state_id == job.worker_id
                    else report_window_key(
                        due_at, tenant.timezone, job.schedule_id, job.schedule
                    )
                )
                # Skip stale backlog windows after downtime; execute at most one
                # overdue window, then schedule the next future occurrence.
                next_at = next_report_occurrence(now, tenant.timezone, job.schedule)
                delivery_handler = self.delivery_handler
                if delivery_handler is not None and job.output_settings is not None:
                    delivery_config = dict(tenant.config)
                    delivery_config["output_settings"] = job.output_settings
                    delivery_config["outputs"] = [
                        "files",
                        *(
                            ["email"]
                            if isinstance(job.output_settings.get("email"), dict)
                            else []
                        ),
                    ]
                    delivery_tenant = replace(tenant, config=delivery_config)

                    def scheduled_delivery(
                        _tenant: TenantRecord,
                        run_id: str,
                        result: dict[str, Any],
                        *,
                        configured_tenant: TenantRecord = delivery_tenant,
                        configured_handler: Any = delivery_handler,
                    ) -> list[dict[str, Any]]:
                        return configured_handler(configured_tenant, run_id, result)

                else:
                    scheduled_delivery = delivery_handler
                try:
                    run_id, result = dispatch_worker(
                        self.store,
                        self.runner,
                        tenant,
                        job.worker_id,
                        job.inputs,
                        key,
                        max_attempts=self.max_attempts,
                        retry_delay_seconds=self.retry_delay_seconds,
                        sleeper=self.sleeper,
                        delivery_handler=scheduled_delivery,
                        run_lease_seconds=self.run_lease_seconds,
                    )
                except DuplicateRun as error:
                    run = error.record
                    status = run.status if run else "duplicate"
                    self.store.upsert_schedule_state(
                        tenant.tenant_id,
                        job.state_id,
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
                            "worker_id": job.worker_id,
                            "schedule_id": job.schedule_id,
                            "status": "duplicate_suppressed",
                            "run_id": run.run_id if run else None,
                        }
                    )
                except RunExecutionFailed as error:
                    attempts = int(error.result.get("attempts", self.max_attempts))
                    detail = (error.result.get("error") or {}).get("detail")
                    self.store.upsert_schedule_state(
                        tenant.tenant_id,
                        job.state_id,
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
                            "worker_id": job.worker_id,
                            "schedule_id": job.schedule_id,
                            "status": "failed",
                            "run_id": error.run_id,
                            "attempts": attempts,
                        }
                    )
                except TenantStoreError as error:
                    detail = str(error)[:500]
                    self.store.upsert_schedule_state(
                        tenant.tenant_id,
                        job.state_id,
                        next_run_at=next_at.isoformat(),
                        last_window_key=key,
                        last_status="failed",
                        last_error=detail,
                    )
                    events.append(
                        {
                            "tenant_id": tenant.tenant_id,
                            "worker_id": job.worker_id,
                            "schedule_id": job.schedule_id,
                            "status": "failed",
                            "run_id": None,
                            "attempts": 0,
                        }
                    )
                else:
                    attempts = int(result.get("attempts", 1))
                    self.store.upsert_schedule_state(
                        tenant.tenant_id,
                        job.state_id,
                        next_run_at=next_at.isoformat(),
                        last_window_key=key,
                        last_run_id=run_id,
                        last_status="completed",
                        attempt_count=attempts,
                    )
                    events.append(
                        {
                            "tenant_id": tenant.tenant_id,
                            "worker_id": job.worker_id,
                            "schedule_id": job.schedule_id,
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
    except Exception as error:  # noqa: BLE001 - heartbeat must record boundary failures
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
