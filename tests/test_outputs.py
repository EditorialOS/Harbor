import json
import urllib.error

import pytest

from harbor.outputs import (
    AdapterReceipt,
    DeliveryCoordinator,
    DeliveryError,
    OutputMessage,
    ResendEmailAdapter,
    render_markdown_email,
    validate_email_recipient,
)
from harbor.tenant_store import TenantStore


def _configured_store(tmp_path):
    store = TenantStore(f"sqlite:///{tmp_path / 'outputs.db'}")
    store.create_tenant(
        "acme",
        "Acme",
        "UTC",
        {
            "workers": ["newsletter-intelligence"],
            "connections": [],
            "outputs": ["files"],
        },
    )
    store.set_sprite("acme", "harbor-acme")
    store.configure_email_output(
        "acme",
        enabled=True,
        recipients=["owner@example.com"],
        subject_prefix="Morning brief",
    )
    assert store.claim_run(
        "run_email", "acme", "newsletter-intelligence", "email-window"
    )
    return store


class ReportRunner:
    def __init__(self):
        self.reads = []

    def read_report(self, sprite_name, report_path):
        self.reads.append((sprite_name, report_path))
        return "# Intelligence\n\n- **Growth:** <strong>safe</strong>\n"


class RecordingAdapter:
    id = "email"

    def __init__(self, *, fail_once=False):
        self.calls = []
        self.fail_once = fail_once

    def deliver(self, message, recipients, idempotency_key):
        self.calls.append((message, recipients, idempotency_key))
        if self.fail_once and len(self.calls) == 1:
            raise RuntimeError("Bearer super-secret-provider-key")
        return AdapterReceipt("provider-message-123")


def test_markdown_renderer_produces_text_and_escaped_html():
    text, rendered = render_markdown_email(
        "# Report\n\n- **Growth:** <script>alert(1)</script>\n"
    )

    assert "• Growth: <script>alert(1)</script>" in text
    assert "<h1>Report</h1>" in rendered
    assert "<strong>Growth:</strong>" in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "<script>" not in rendered


def test_recipient_validation_rejects_header_injection_and_invalid_addresses():
    assert validate_email_recipient(" owner@example.com ") == "owner@example.com"
    for invalid in ("not-an-email", "owner@localhost", "a@example.com\nBcc: bad@test.io"):
        with pytest.raises(DeliveryError, match="recipient is invalid"):
            validate_email_recipient(invalid)


def test_resend_adapter_uses_authenticated_idempotent_api_request(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"id":"email_123"}'

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    receipt = ResendEmailAdapter(
        api_key="secret-key", sender="Harbor <reports@example.com>"
    ).deliver(
        OutputMessage("Subject", "plain", "<p>html</p>"),
        ["owner@example.com"],
        "delivery-v1:run:email:fingerprint",
    )

    request = captured["request"]
    assert request.full_url == "https://api.resend.com/emails"
    assert request.get_method() == "POST"
    assert request.headers["Authorization"] == "Bearer secret-key"
    assert request.headers["Idempotency-key"] == "delivery-v1:run:email:fingerprint"
    assert captured["timeout"] == 30
    assert json.loads(request.data) == {
        "from": "Harbor <reports@example.com>",
        "to": ["owner@example.com"],
        "subject": "Subject",
        "text": "plain",
        "html": "<p>html</p>",
    }
    assert receipt.provider_message_id == "email_123"


def test_resend_adapter_surfaces_sanitized_http_failure(monkeypatch):
    def fail(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "unauthorized", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(DeliveryError, match="HTTP 401") as error:
        ResendEmailAdapter(api_key="secret-key", sender="reports@example.com").deliver(
            OutputMessage("Subject", "plain", "<p>html</p>"),
            ["owner@example.com"],
            "delivery-v1:test",
        )
    assert "secret-key" not in str(error.value)


def test_delivery_is_durable_idempotent_and_does_not_expose_recipient(tmp_path):
    store = _configured_store(tmp_path)
    runner = ReportRunner()
    adapter = RecordingAdapter()
    coordinator = DeliveryCoordinator(store, runner, email_adapter=adapter)
    result = {
        "status": "completed",
        "deliverables": ["/workspace/Work/reports/report.md"],
    }

    first = coordinator.deliver(store.get("acme"), "run_email", result)
    second = coordinator.deliver(store.get("acme"), "run_email", result)

    assert len(adapter.calls) == 1
    assert first[0]["status"] == "delivered"
    assert first[0]["duplicate_suppressed"] is False
    assert second[0]["duplicate_suppressed"] is True
    assert "owner@example.com" not in json.dumps(first + second)
    record = store.get_delivery(first[0]["delivery_id"])
    assert record.provider_message_id == "provider-message-123"
    assert record.attempt_count == 1
    assert "owner@example.com" not in repr(record)
    assert {event.action for event in store.list_audit("acme")} >= {
        "delivery.claimed",
        "delivery.finished",
    }


def test_failed_delivery_is_persisted_and_retried_with_same_key(tmp_path, monkeypatch):
    store = _configured_store(tmp_path)
    adapter = RecordingAdapter(fail_once=True)
    coordinator = DeliveryCoordinator(store, ReportRunner(), email_adapter=adapter)
    result = {
        "status": "completed",
        "deliverables": ["/workspace/Work/reports/report.md"],
    }
    monkeypatch.setenv("RESEND_API_KEY", "super-secret-provider-key")

    with pytest.raises(DeliveryError):
        coordinator.deliver(store.get("acme"), "run_email", result)
    existing = store.get_delivery_by_idempotency(
        "acme", "email", adapter.calls[0][2]
    )
    assert existing is not None
    assert existing.status == "failed"
    assert existing.attempt_count == 1
    assert "super-secret-provider-key" not in (existing.last_error or "")

    delivered = coordinator.deliver(store.get("acme"), "run_email", result)
    assert len(adapter.calls) == 2
    assert adapter.calls[0][2] == adapter.calls[1][2]
    assert delivered[0]["status"] == "delivered"
    assert store.get_delivery(existing.delivery_id).attempt_count == 2


def test_files_only_tenant_skips_report_read_and_adapter(tmp_path):
    store = TenantStore(f"sqlite:///{tmp_path / 'files-only.db'}")
    store.create_tenant(
        "acme",
        "Acme",
        "UTC",
        {"workers": ["newsletter-intelligence"], "outputs": ["files"]},
    )
    runner = ReportRunner()
    adapter = RecordingAdapter()

    assert (
        DeliveryCoordinator(store, runner, email_adapter=adapter).deliver(
            store.get("acme"), "unused", {"status": "completed"}
        )
        == []
    )
    assert runner.reads == []
    assert adapter.calls == []
