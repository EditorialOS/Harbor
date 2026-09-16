import datetime as dt

import pytest

from harbor.scheduler import (
    DailySchedule,
    Scheduler,
    configured_jobs,
    monitored_tick,
    next_occurrence,
    next_report_occurrence,
    parse_report_schedule,
    report_window_key,
    window_key,
)
from harbor.tenant_store import TenantStore


class SuccessfulRunner:
    def __init__(self):
        self.calls = []

    def run(self, sprite_name, run_spec):
        self.calls.append((sprite_name, run_spec))
        return {"status": "completed", "summary": "scheduled report"}


def _scheduled_store(tmp_path):
    store = TenantStore(f"sqlite:///{tmp_path / 'scheduler.db'}")
    store.create_tenant(
        "acme",
        "Acme",
        "America/Los_Angeles",
        {
            "workers": ["newsletter-intelligence"],
            "schedule": {"newsletter-intelligence": {"hour": 6, "minute": 30}},
            "connections": [],
        },
    )
    store.set_sprite("acme", "harbor-acme")
    return store


def test_timezone_schedule_initializes_then_runs_due_window_once(tmp_path):
    store = _scheduled_store(tmp_path)
    runner = SuccessfulRunner()
    scheduler = Scheduler(store, runner, sleeper=lambda _: None)
    before = dt.datetime(2026, 9, 5, 12, 0, tzinfo=dt.timezone.utc)

    initialized = scheduler.tick(before)
    state = store.get_schedule_state("acme", "newsletter-intelligence")
    assert initialized[0]["status"] == "scheduled"
    assert state is not None
    assert state.next_run_at == "2026-09-05T13:30:00+00:00"

    completed = scheduler.tick(dt.datetime(2026, 9, 5, 13, 31, tzinfo=dt.timezone.utc))
    assert completed[0]["status"] == "completed"
    assert len(runner.calls) == 1
    run_id = completed[0]["run_id"]
    state = store.get_schedule_state("acme", "newsletter-intelligence")
    assert state is not None
    assert state.last_run_id == run_id
    assert state.last_status == "completed"
    assert state.next_run_at == "2026-09-06T13:30:00+00:00"

    assert scheduler.tick(dt.datetime(2026, 9, 5, 13, 32, tzinfo=dt.timezone.utc)) == []
    assert len(runner.calls) == 1


def test_legacy_schedule_uses_selected_source_only(tmp_path):
    store = _scheduled_store(tmp_path)
    store.update_worker_schedule(
        "acme",
        "newsletter-intelligence",
        {"hour": 6, "minute": 30, "connection_id": "kit-acme"},
        "America/Los_Angeles",
        "2026-09-05T13:30:00+00:00",
    )

    jobs = configured_jobs(store.get("acme"))

    assert len(jobs) == 1
    assert jobs[0].inputs == {"connection_id": "kit-acme"}


def test_schedule_window_key_is_stable_and_timezone_specific():
    due = dt.datetime(2026, 9, 5, 13, 30, tzinfo=dt.timezone.utc)
    schedule = DailySchedule(6, 30)
    assert window_key(due, "America/Los_Angeles", schedule) == (
        "schedule-v1:2026-09-05:0630:America/Los_Angeles"
    )
    assert next_occurrence(
        dt.datetime(2026, 9, 5, 13, 31, tzinfo=dt.timezone.utc),
        "America/Los_Angeles",
        schedule,
    ) == dt.datetime(2026, 9, 6, 13, 30, tzinfo=dt.timezone.utc)


def test_scheduler_skips_backlog_after_a_long_outage(tmp_path):
    store = _scheduled_store(tmp_path)
    runner = SuccessfulRunner()
    scheduler = Scheduler(store, runner, sleeper=lambda _: None)
    store.upsert_schedule_state(
        "acme",
        "newsletter-intelligence",
        next_run_at="2026-09-01T13:30:00+00:00",
        last_status="scheduled",
    )

    events = scheduler.tick(dt.datetime(2026, 9, 5, 20, 0, tzinfo=dt.timezone.utc))

    assert events[0]["status"] == "completed"
    assert len(runner.calls) == 1
    state = store.get_schedule_state("acme", "newsletter-intelligence")
    assert state is not None
    assert state.next_run_at == "2026-09-06T13:30:00+00:00"


def test_invalid_schedule_is_persisted_and_throttled(tmp_path):
    store = TenantStore(f"sqlite:///{tmp_path / 'bad-scheduler.db'}")
    store.create_tenant(
        "bad",
        "Bad",
        "UTC",
        {
            "workers": ["newsletter-intelligence"],
            "schedule": {"newsletter-intelligence": {"hour": 99}},
            "connections": [],
        },
    )
    scheduler = Scheduler(store, SuccessfulRunner(), sleeper=lambda _: None)
    now = dt.datetime(2026, 9, 5, 20, 0, tzinfo=dt.timezone.utc)

    first = scheduler.tick(now)
    second = scheduler.tick(now + dt.timedelta(minutes=1))

    assert first[0]["status"] == "configuration_failed"
    assert second == []
    state = store.get_schedule_state("bad", "newsletter-intelligence")
    assert state is not None
    assert state.last_status == "configuration_failed"


def test_missing_sprite_failure_is_persisted_without_crashing_tick(tmp_path):
    store = TenantStore(f"sqlite:///{tmp_path / 'unprovisioned.db'}")
    store.create_tenant(
        "pending",
        "Pending",
        "UTC",
        {
            "workers": ["newsletter-intelligence"],
            "schedule": {"newsletter-intelligence": {"hour": 6, "minute": 30}},
            "connections": [],
        },
    )
    scheduler = Scheduler(store, SuccessfulRunner(), sleeper=lambda _: None)
    store.upsert_schedule_state(
        "pending",
        "newsletter-intelligence",
        next_run_at="2026-09-05T06:30:00+00:00",
        last_status="scheduled",
    )

    events = scheduler.tick(dt.datetime(2026, 9, 5, 6, 31, tzinfo=dt.timezone.utc))

    assert events[0]["status"] == "failed"
    assert events[0]["run_id"] is None
    state = store.get_schedule_state("pending", "newsletter-intelligence")
    assert state is not None
    assert state.last_status == "failed"
    assert "not provisioned" in (state.last_error or "")


def test_monitored_tick_records_healthy_and_failed_heartbeats(tmp_path):
    store = _scheduled_store(tmp_path)
    scheduler = Scheduler(store, SuccessfulRunner(), sleeper=lambda _: None)

    assert monitored_tick(scheduler, store)[0]["status"] == "scheduled"
    heartbeat = store.get_service_heartbeat("scheduler")
    assert heartbeat is not None
    assert heartbeat.status == "healthy"
    assert heartbeat.metadata == {"event_count": 1}

    class BrokenScheduler:
        def tick(self):
            raise RuntimeError("scheduler failed")

    with pytest.raises(RuntimeError, match="scheduler failed"):
        monitored_tick(BrokenScheduler(), store)
    heartbeat = store.get_service_heartbeat("scheduler")
    assert heartbeat is not None
    assert heartbeat.status == "failed"
    assert heartbeat.metadata == {"error_type": "RuntimeError"}


def test_report_recurrences_support_weekly_monthly_quarterly_and_custom():
    now = dt.datetime(2026, 9, 6, 12, 0, tzinfo=dt.timezone.utc)  # Sunday
    weekly = parse_report_schedule(
        {"frequency": "weekly", "weekday": "Monday", "hour": 6, "minute": 15}
    )
    monthly = parse_report_schedule(
        {"frequency": "monthly", "first_weekday": True, "hour": 7}
    )
    quarterly = parse_report_schedule(
        {"frequency": "quarterly", "day": 2, "hour": 8}
    )
    custom = parse_report_schedule(
        {"frequency": "custom", "weekdays": ["Tuesday", "Thursday"], "hour": 9}
    )

    assert next_report_occurrence(now, "UTC", weekly) == dt.datetime(
        2026, 9, 7, 6, 15, tzinfo=dt.timezone.utc
    )
    assert next_report_occurrence(now, "UTC", monthly) == dt.datetime(
        2026, 10, 1, 7, 0, tzinfo=dt.timezone.utc
    )
    assert next_report_occurrence(now, "UTC", quarterly) == dt.datetime(
        2026, 10, 2, 8, 0, tzinfo=dt.timezone.utc
    )
    assert next_report_occurrence(now, "UTC", custom) == dt.datetime(
        2026, 9, 8, 9, 0, tzinfo=dt.timezone.utc
    )
    assert report_window_key(
        dt.datetime(2026, 9, 7, 6, 15, tzinfo=dt.timezone.utc),
        "UTC",
        "weekly-review",
        weekly,
    ) == "report-schedule-v1:weekly-review:2026-09-07:0615:UTC"


def test_multiple_reports_keep_independent_timeframes_state_and_recipients(tmp_path):
    store = TenantStore(f"sqlite:///{tmp_path / 'reports.db'}")
    store.create_tenant(
        "reports",
        "Reports",
        "UTC",
        {
            "workers": ["newsletter-intelligence"],
            "connections": [],
            "outputs": ["files"],
            "report_schedules": [
                {
                    "id": "daily-pulse",
                    "worker_id": "newsletter-intelligence",
                    "schedule": {"frequency": "daily", "hour": 6},
                    "input": {"timeframe": "yesterday", "view": "portfolio"},
                    "output_settings": {
                        "email": {
                            "recipients": ["daily@example.com"],
                            "subject_prefix": "Daily Pulse",
                        }
                    },
                },
                {
                    "id": "weekly-review",
                    "worker_id": "newsletter-intelligence",
                    "schedule": {
                        "frequency": "weekly",
                        "weekday": "Monday",
                        "hour": 6,
                    },
                    "input": {"timeframe": "last_7_days", "view": "portfolio"},
                    "output_settings": {
                        "email": {
                            "recipients": ["weekly@example.com"],
                            "subject_prefix": "Weekly Review",
                        }
                    },
                },
            ],
        },
    )
    store.set_sprite("reports", "harbor-reports")
    runner = SuccessfulRunner()
    deliveries = []

    def deliver(tenant, run_id, result):
        deliveries.append(tenant.config["output_settings"]["email"])
        return []

    scheduler = Scheduler(
        store, runner, sleeper=lambda _: None, delivery_handler=deliver
    )
    now = dt.datetime(2026, 9, 6, 5, 0, tzinfo=dt.timezone.utc)
    initialized = scheduler.tick(now)
    assert {event["schedule_id"] for event in initialized} == {
        "daily-pulse",
        "weekly-review",
    }
    due = "2026-09-07T06:00:00+00:00"
    for state_id in ("report:daily-pulse", "report:weekly-review"):
        store.upsert_schedule_state(
            "reports", state_id, next_run_at=due, last_status="scheduled"
        )

    completed = scheduler.tick(
        dt.datetime(2026, 9, 7, 6, 1, tzinfo=dt.timezone.utc)
    )

    assert {event["schedule_id"] for event in completed} == {
        "daily-pulse",
        "weekly-review",
    }
    assert [call[1]["input"]["timeframe"] for call in runner.calls] == [
        "yesterday",
        "last_7_days",
    ]
    assert [settings["recipients"][0] for settings in deliveries] == [
        "daily@example.com",
        "weekly@example.com",
    ]
    assert store.get_schedule_state("reports", "report:daily-pulse") is not None
    assert store.get_schedule_state("reports", "report:weekly-review") is not None
