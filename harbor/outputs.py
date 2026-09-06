"""Infrastructure-independent output adapters and durable delivery coordination."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import secrets
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from .sprite_runner import SpriteRunner
from .tenant_store import DeliveryRecord, TenantRecord, TenantStore, TenantStoreError


class DeliveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class OutputMessage:
    subject: str
    text: str
    html: str


@dataclass(frozen=True)
class AdapterReceipt:
    provider_message_id: str


class OutputAdapter(Protocol):
    id: str

    def deliver(
        self,
        message: OutputMessage,
        recipients: list[str],
        idempotency_key: str,
    ) -> AdapterReceipt: ...


_EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


def validate_email_recipient(value: str) -> str:
    candidate = value.strip()
    if len(candidate) > 254 or "\r" in candidate or "\n" in candidate:
        raise DeliveryError("email recipient is invalid")
    if not _EMAIL_PATTERN.fullmatch(candidate):
        raise DeliveryError("email recipient is invalid")
    return candidate


def _inline_markdown(value: str) -> str:
    escaped = html.escape(value, quote=True)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def render_markdown_email(markdown: str) -> tuple[str, str]:
    """Render Harbor's constrained report Markdown as safe HTML and plain text."""
    html_lines = []
    text_lines = []
    in_list = False
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        plain = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        if plain.startswith("# "):
            plain = plain[2:]
        elif plain.startswith("## "):
            plain = plain[3:]
        elif plain.startswith("- "):
            plain = "• " + plain[2:]
        elif plain == "---":
            plain = ""
        text_lines.append(plain)

        if line.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{_inline_markdown(line[2:])}</li>")
            continue
        if in_list:
            html_lines.append("</ul>")
            in_list = False
        if line.startswith("## "):
            html_lines.append(f"<h2>{_inline_markdown(line[3:])}</h2>")
        elif line.startswith("# "):
            html_lines.append(f"<h1>{_inline_markdown(line[2:])}</h1>")
        elif line == "---":
            html_lines.append("<hr>")
        elif line:
            html_lines.append(f"<p>{_inline_markdown(line)}</p>")
    if in_list:
        html_lines.append("</ul>")
    body = "\n".join(html_lines)
    html_document = (
        '<!doctype html><html><body style="font-family:-apple-system,BlinkMacSystemFont,'
        "Segoe UI,sans-serif;line-height:1.5;color:#171717;max-width:680px;margin:auto;"
        f">{body}</body></html>"
    )
    return "\n".join(text_lines).strip() + "\n", html_document


class ResendEmailAdapter:
    id = "email"

    def __init__(
        self,
        api_key: str | None = None,
        sender: str | None = None,
        api_base: str = "https://api.resend.com",
    ):
        self.api_key = api_key or os.environ.get("RESEND_API_KEY")
        self.sender = sender or os.environ.get("HARBOR_EMAIL_FROM")
        self.api_base = api_base.rstrip("/")
        if not self.api_key:
            raise DeliveryError("RESEND_API_KEY is not configured")
        if not self.sender or "\r" in self.sender or "\n" in self.sender:
            raise DeliveryError("HARBOR_EMAIL_FROM is not configured correctly")

    def deliver(
        self,
        message: OutputMessage,
        recipients: list[str],
        idempotency_key: str,
    ) -> AdapterReceipt:
        payload = json.dumps(
            {
                "from": self.sender,
                "to": recipients,
                "subject": message.subject,
                "text": message.text,
                "html": message.html,
            }
        ).encode()
        request = urllib.request.Request(
            f"{self.api_base}/emails",
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read())
        except urllib.error.HTTPError as error:
            raise DeliveryError(
                f"email provider returned HTTP {error.code}"
            ) from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise DeliveryError("email provider is unreachable") from error
        provider_message_id = result.get("id")
        if not isinstance(provider_message_id, str) or not provider_message_id:
            raise DeliveryError("email provider returned an invalid response")
        return AdapterReceipt(provider_message_id)


def _delivery_result(record: DeliveryRecord, duplicate: bool) -> dict[str, Any]:
    return {
        "delivery_id": record.delivery_id,
        "adapter": record.adapter,
        "status": record.status,
        "attempt_count": record.attempt_count,
        "duplicate_suppressed": duplicate,
    }


def _safe_delivery_error(error: Exception) -> str:
    detail = f"{type(error).__name__}: {error}"
    for variable in ("RESEND_API_KEY",):
        secret = os.environ.get(variable)
        if secret:
            detail = detail.replace(secret, "[REDACTED]")
    detail = re.sub(
        r"(?i)(authorization|bearer|api[_-]?key|access[_-]?token)(\s*[:=]?\s*)\S+",
        r"\1\2[REDACTED]",
        detail,
    )
    detail = re.sub(r"(https?://)[^/@\s]+:[^/@\s]+@", r"\1[REDACTED]@", detail)
    return detail[:500]


class DeliveryCoordinator:
    def __init__(
        self,
        store: TenantStore,
        runner: SpriteRunner,
        *,
        email_adapter: OutputAdapter | None = None,
    ):
        self.store = store
        self.runner = runner
        self.email_adapter = email_adapter

    def _email_adapter(self) -> OutputAdapter:
        return self.email_adapter or ResendEmailAdapter()

    def deliver(
        self,
        tenant: TenantRecord,
        run_id: str,
        worker_result: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if "email" not in tenant.config.get("outputs", []):
            return []
        settings = (tenant.config.get("output_settings") or {}).get("email") or {}
        raw_recipients = settings.get("recipients") or []
        if not isinstance(raw_recipients, list) or not 1 <= len(raw_recipients) <= 50:
            raise DeliveryError("email output requires 1 through 50 recipients")
        recipients = [validate_email_recipient(str(item)) for item in raw_recipients]
        deliverables = worker_result.get("deliverables") or []
        if len(deliverables) != 1 or not isinstance(deliverables[0], str):
            raise DeliveryError("email output requires exactly one report deliverable")
        markdown = self.runner.read_report(tenant.sprite_name or "", deliverables[0])
        text, rendered_html = render_markdown_email(markdown)
        subject_prefix = str(settings.get("subject_prefix") or "Harbor")
        if "\r" in subject_prefix or "\n" in subject_prefix:
            raise DeliveryError("email subject prefix is invalid")
        message = OutputMessage(
            subject=f"{subject_prefix} — {tenant.name}",
            text=text,
            html=rendered_html,
        )
        destination_fingerprint = hashlib.sha256(
            "\n".join(sorted(item.lower() for item in recipients)).encode()
        ).hexdigest()
        idempotency_key = f"delivery-v1:{run_id}:email:{destination_fingerprint[:16]}"
        existing = self.store.get_delivery_by_idempotency(
            tenant.tenant_id, "email", idempotency_key
        )
        if existing and existing.status == "delivered":
            return [_delivery_result(existing, True)]

        delivery_id = existing.delivery_id if existing else "delivery_" + secrets.token_hex(12)
        if existing is None:
            claimed = self.store.claim_delivery(
                delivery_id,
                tenant.tenant_id,
                run_id,
                "email",
                destination_fingerprint,
                idempotency_key,
            )
            if not claimed:
                existing = self.store.get_delivery_by_idempotency(
                    tenant.tenant_id, "email", idempotency_key
                )
                if existing and existing.status == "delivered":
                    return [_delivery_result(existing, True)]
                if existing is None:
                    raise TenantStoreError("delivery claim was not persisted")
                delivery_id = existing.delivery_id

        self.store.begin_delivery_attempt(delivery_id)
        try:
            receipt = self._email_adapter().deliver(
                message, recipients, idempotency_key
            )
        except Exception as error:
            detail = _safe_delivery_error(error)
            self.store.finish_delivery(delivery_id, "failed", last_error=detail)
            raise DeliveryError(detail) from error
        delivered = self.store.finish_delivery(
            delivery_id,
            "delivered",
            provider_message_id=receipt.provider_message_id,
        )
        return [_delivery_result(delivered, False)]
