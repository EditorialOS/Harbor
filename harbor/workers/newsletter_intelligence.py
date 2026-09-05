"""The first commercial Harbor worker: Newsletter Intelligence.

It turns a connected newsletter account into an unprompted, date-stamped
morning intelligence report. v0.9 deliberately makes the interpretation
mostly deterministic so the product can be tested before adding model cost.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from .. import beehiiv_client
from ..config import TenantConfig
from ..reporting import write_report, write_run
from ..secrets import resolve
from ..worker import WorkerResult, register


def _pct(v: Any) -> str:
    return "—" if v is None else f"{float(v):.1%}"


def _delta(value: float | None, baseline: float | None) -> tuple[float | None, str]:
    if value is None or baseline in (None, 0):
        return None, "no baseline"
    d = value - baseline
    if d > 0.005:
        label = "above"
    elif d < -0.005:
        label = "below"
    else:
        label = "in line with"
    return d, label


def _derive(data: dict[str, Any]) -> dict[str, Any]:
    posts = [p for p in data.get("recent_posts", []) if p]
    latest = posts[0] if posts else {}
    comparable_open = [p for p in posts if p.get("open_rate") is not None]
    comparable_click = [p for p in posts if p.get("click_rate") is not None]
    best_open = max(comparable_open, key=lambda p: p["open_rate"], default={})
    best_click = max(comparable_click, key=lambda p: p["click_rate"], default={})
    open_delta, open_label = _delta(latest.get("open_rate"), data.get("avg_open_rate"))
    click_delta, click_label = _delta(
        latest.get("click_rate"), data.get("avg_click_rate")
    )
    return {
        "latest": latest,
        "best_open": best_open,
        "best_click": best_click,
        "open_delta": open_delta,
        "open_label": open_label,
        "click_delta": click_delta,
        "click_label": click_label,
    }


def _recommendations(data: dict[str, Any], d: dict[str, Any]) -> list[str]:
    out: list[str] = []
    latest = d["latest"]
    if not latest:
        return [
            "Publish at least one issue before Harbor can establish a useful recent-performance signal."
        ]

    if d["open_delta"] is not None:
        if d["open_delta"] >= 0.01:
            out.append(
                "Preserve the latest issue's subject-line pattern for the next send; opens are materially above the publication baseline."
            )
        elif d["open_delta"] <= -0.01:
            out.append(
                "Test a different subject-line approach on the next send; the latest open rate is materially below the publication baseline."
            )
        else:
            out.append(
                "Open performance is close to baseline; treat the next send as an opportunity to test one subject-line variable rather than changing several things at once."
            )

    if d["click_delta"] is not None:
        if d["click_delta"] >= 0.005:
            out.append(
                "Keep the latest issue's link density and CTA treatment as a control; click performance is above baseline."
            )
        elif d["click_delta"] <= -0.005:
            out.append(
                "Review CTA placement and link intent before the next send; clicks are under the publication baseline."
            )

    if d["best_open"] and d["best_open"].get("title") != latest.get("title"):
        out.append(
            f"Revisit the framing of “{d['best_open'].get('title')}”; it is the strongest recent opener and should inform future packaging."
        )

    return out[:3]


def _markdown(
    tenant: TenantConfig, data: dict[str, Any], derived: dict[str, Any]
) -> str:
    today = dt.datetime.now(dt.timezone.utc).date().strftime("%A, %B %d, %Y")
    latest = derived["latest"]
    recommendations = _recommendations(data, derived)
    mock_note = (
        "\n> Development mode: this report uses Harbor's shaped mock data because no live beehiiv key was resolved.\n"
        if data.get("_mock")
        else ""
    )

    lines = [
        f"# Harbor Morning Intelligence — {today}",
        "",
        f"**{data.get('publication_name') or tenant.name}**",
        mock_note.rstrip(),
        "",
        "## Yesterday / latest send",
        f"- Subscribers: {data.get('active_subscribers', '—')}",
        f"- Publication baseline: {_pct(data.get('avg_open_rate'))} open · {_pct(data.get('avg_click_rate'))} click",
    ]
    if latest:
        lines += [
            f"- Latest: **{latest.get('title') or 'Untitled'}** — {_pct(latest.get('open_rate'))} open · {_pct(latest.get('click_rate'))} click",
            "",
            "## What matters",
            f"- Opens are **{derived['open_label']}** the publication baseline"
            + (
                f" ({derived['open_delta']:+.1%})."
                if derived["open_delta"] is not None
                else "."
            ),
            f"- Clicks are **{derived['click_label']}** the publication baseline"
            + (
                f" ({derived['click_delta']:+.1%})."
                if derived["click_delta"] is not None
                else "."
            ),
        ]
    if derived["best_open"]:
        lines.append(
            f"- Strongest recent opener: **{derived['best_open'].get('title')}** at {_pct(derived['best_open'].get('open_rate'))}."
        )
    if derived["best_click"]:
        lines.append(
            f"- Strongest recent click performer: **{derived['best_click'].get('title')}** at {_pct(derived['best_click'].get('click_rate'))}."
        )

    lines += ["", "## Do next"]
    lines += [f"- {r}" for r in recommendations]
    lines += ["", "---", "Harbor · Newsletter Intelligence"]
    return "\n".join(line for line in lines if line is not None) + "\n"


class NewsletterIntelligenceWorker:
    id = "newsletter-intelligence"
    label = "Newsletter Intelligence"

    def run(
        self, tenant: TenantConfig, inputs: dict[str, Any] | None = None
    ) -> WorkerResult:
        inputs = inputs or {}
        if not tenant.worker_enabled(self.id):
            return WorkerResult(
                self.id, "disabled", "Worker is not enabled for this tenant."
            )

        conn = tenant.connection("beehiiv")
        auth_mode = conn.settings.get("auth_mode", "bearer")
        api_key = (
            resolve(conn.secret_ref, required=False) if auth_mode == "bearer" else None
        )
        publication_id = inputs.get("publication_id") or conn.settings.get(
            "publication_id"
        )
        if not publication_id:
            return WorkerResult(self.id, "failed", "beehiiv publication_id is missing")

        recent_posts = int(
            inputs.get("recent_posts") or conn.settings.get("recent_posts", 5)
        )
        base_url = conn.settings.get("gateway_base_url") or conn.settings.get(
            "base_url"
        )
        allow_mock = str(inputs.get("mode", "")).lower() == "mock"
        data = beehiiv_client.publication_performance(
            publication_id,
            recent_posts,
            api_key=api_key,
            base_url=base_url,
            auth_mode=auth_mode,
            allow_mock=allow_mock,
        )
        derived = _derive(data)
        report = _markdown(tenant, data, derived)
        report_path = write_report(tenant.workspace, "newsletter-intelligence", report)

        run_id = inputs.get("_harbor_run_id") or (
            f"run_{dt.datetime.now(dt.timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
        )
        run_record = {
            "run_id": run_id,
            "idempotency_key_hash": inputs.get("_harbor_idempotency_key_hash"),
            "tenant_id": tenant.tenant_id,
            "worker": self.id,
            "status": "completed",
            "mock": bool(data.get("_mock")),
            "report": report_path,
            "source": "beehiiv-api" if not data.get("_mock") else "beehiiv-mock",
            "metrics": data,
            "derived": derived,
        }
        run_path = write_run(tenant.workspace, run_record, run_id)
        warnings = []
        if data.get("_mock"):
            warnings.append(
                "Explicit development mock mode was requested; no production run should contain mock data."
            )

        return WorkerResult(
            worker_id=self.id,
            status="completed",
            summary=f"Created morning intelligence report for {data.get('publication_name') or tenant.name}.",
            data={"metrics": data, "derived": derived, "run_record": run_path},
            deliverables=[report_path],
            warnings=warnings,
        )


WORKER = register(NewsletterIntelligenceWorker())
