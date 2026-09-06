import pytest

from harbor.dispatch import DuplicateRun, RunExecutionFailed, dispatch_worker
from harbor.sprites_client import SpriteError
from harbor.tenant_store import TenantStore


def _store_and_tenant(tmp_path):
    store = TenantStore(f"sqlite:///{tmp_path / 'dispatch.db'}")
    store.create_tenant(
        "acme",
        "Acme",
        "UTC",
        {"workers": ["newsletter-intelligence"], "connections": []},
    )
    store.set_sprite("acme", "harbor-acme")
    return store, store.get("acme")


def test_dispatch_retries_with_one_run_id(tmp_path):
    store, tenant = _store_and_tenant(tmp_path)

    class FlakyRunner:
        def __init__(self):
            self.calls = []

        def run(self, sprite_name, run_spec):
            self.calls.append(run_spec["run_id"])
            if len(self.calls) < 3:
                raise SpriteError("temporary Sprite failure")
            return {"status": "completed", "summary": "ok"}

    runner = FlakyRunner()
    run_id, result = dispatch_worker(
        store,
        runner,
        tenant,
        "newsletter-intelligence",
        {},
        "schedule-window",
        max_attempts=3,
        retry_delay_seconds=1,
        sleeper=lambda _: None,
    )

    assert runner.calls == [run_id, run_id, run_id]
    assert result["attempts"] == 3
    record = store.get_run_by_idempotency(
        "acme", "newsletter-intelligence", "schedule-window"
    )
    assert record is not None
    assert record.status == "completed"
    assert record.attempt_count == 3
    assert record.last_error is None

    with pytest.raises(DuplicateRun):
        dispatch_worker(
            store,
            runner,
            tenant,
            "newsletter-intelligence",
            {},
            "schedule-window",
        )


def test_dispatch_rejects_secret_shaped_worker_result(tmp_path):
    store, tenant = _store_and_tenant(tmp_path)

    class UnsafeRunner:
        def run(self, sprite_name, run_spec):
            return {"status": "completed", "api_key": "must-not-persist"}

    with pytest.raises(RunExecutionFailed) as error:
        dispatch_worker(
            store,
            UnsafeRunner(),
            tenant,
            "newsletter-intelligence",
            {},
            "unsafe-window",
        )

    record = store.get_run_by_idempotency(
        "acme", "newsletter-intelligence", "unsafe-window"
    )
    assert record is not None
    assert record.status == "failed"
    assert "must-not-persist" not in str(record.result)
    assert "must-not-persist" not in (record.last_error or "")
    assert error.value.result["status"] == "failed"


def test_dispatch_retries_delivery_with_same_run_and_worker_spec(tmp_path):
    store, tenant = _store_and_tenant(tmp_path)

    class Runner:
        def __init__(self):
            self.run_ids = []

        def run(self, sprite_name, run_spec):
            self.run_ids.append(run_spec["run_id"])
            assert run_spec["outputs"] == ["files"]
            return {
                "status": "completed",
                "deliverables": ["/workspace/Work/reports/report.md"],
            }

    delivery_calls = []

    def delivery_handler(record, run_id, result):
        delivery_calls.append(run_id)
        if len(delivery_calls) == 1:
            raise RuntimeError("provider unavailable")
        return [{"delivery_id": "delivery_1", "status": "delivered"}]

    runner = Runner()
    run_id, result = dispatch_worker(
        store,
        runner,
        tenant,
        "newsletter-intelligence",
        {},
        "delivery-window",
        max_attempts=2,
        delivery_handler=delivery_handler,
    )

    assert runner.run_ids == [run_id, run_id]
    assert delivery_calls == [run_id, run_id]
    assert result["attempts"] == 2
    assert result["deliveries"][0]["status"] == "delivered"


def test_dispatch_recovers_expired_run_lease_with_original_run_id(tmp_path):
    store, tenant = _store_and_tenant(tmp_path)
    assert store.claim_run(
        "run_interrupted",
        "acme",
        "newsletter-intelligence",
        "interrupted-window",
        lease_seconds=60,
    )
    store.begin_run_attempt("run_interrupted", lease_seconds=60)
    with store._connect() as conn:
        conn.execute(
            "UPDATE runs SET lease_expires_at=? WHERE run_id=?",
            ("2020-01-01T00:00:00+00:00", "run_interrupted"),
        )

    class Runner:
        def __init__(self):
            self.run_ids = []

        def run(self, sprite_name, run_spec):
            self.run_ids.append(run_spec["run_id"])
            return {"status": "completed", "summary": "recovered"}

    runner = Runner()
    run_id, result = dispatch_worker(
        store,
        runner,
        tenant,
        "newsletter-intelligence",
        {},
        "interrupted-window",
        max_attempts=3,
        run_lease_seconds=60,
    )

    assert run_id == "run_interrupted"
    assert runner.run_ids == ["run_interrupted"]
    assert result["attempts"] == 2
    record = store.get_run_by_idempotency(
        "acme", "newsletter-intelligence", "interrupted-window"
    )
    assert record is not None
    assert record.status == "completed"
    assert record.attempt_count == 2
    assert record.lease_expires_at is None
    assert "run.reclaimed" in {
        event.action for event in store.list_audit("acme")
    }


def test_dispatch_does_not_recover_an_unexpired_run(tmp_path):
    store, tenant = _store_and_tenant(tmp_path)
    assert store.claim_run(
        "run_active",
        "acme",
        "newsletter-intelligence",
        "active-window",
        lease_seconds=3600,
    )

    with pytest.raises(DuplicateRun) as error:
        dispatch_worker(
            store,
            object(),
            tenant,
            "newsletter-intelligence",
            {},
            "active-window",
            run_lease_seconds=3600,
        )

    assert error.value.record is not None
    assert error.value.record.run_id == "run_active"
