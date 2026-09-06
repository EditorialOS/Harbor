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
