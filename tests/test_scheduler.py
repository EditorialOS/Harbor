import datetime as dt

from harbor.scheduler import DailySchedule, Scheduler, next_occurrence, window_key
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

    events = scheduler.tick(
        dt.datetime(2026, 9, 5, 20, 0, tzinfo=dt.timezone.utc)
    )

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

    events = scheduler.tick(
        dt.datetime(2026, 9, 5, 6, 31, tzinfo=dt.timezone.utc)
    )

    assert events[0]["status"] == "failed"
    assert events[0]["run_id"] is None
    state = store.get_schedule_state("pending", "newsletter-intelligence")
    assert state is not None
    assert state.last_status == "failed"
    assert "not provisioned" in (state.last_error or "")
