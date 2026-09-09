"""Newsletter Intelligence: evidence-based analysis of live newsletter data."""

from __future__ import annotations

import datetime as dt
import json
import statistics
import uuid
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .. import beehiiv_client
from ..config import TenantConfig
from ..reporting import ensure_workspace, write_report, write_run
from ..secrets import resolve
from ..worker import WorkerResult, register

_STATE_FILE = "newsletter-intelligence.json"


def _pct(value: Any) -> str:
    return "unavailable" if value is None else f"{float(value):.1%}"


def _count(value: Any) -> str:
    return "unavailable" if value is None else f"{int(value):,}"


def _delta(value: float | None, baseline: float | None) -> tuple[float | None, str]:
    if value is None or baseline in (None, 0):
        return None, "unavailable"
    difference = float(value) - float(baseline)
    if difference > 0.005:
        label = "above"
    elif difference < -0.005:
        label = "below"
    else:
        label = "in line with"
    return difference, label


def _mean(posts: list[dict[str, Any]], metric: str) -> float | None:
    values = [float(post[metric]) for post in posts if post.get(metric) is not None]
    return statistics.fmean(values) if values else None


def _eligible(posts: list[dict[str, Any]], metric: str) -> list[dict[str, Any]]:
    return [
        post
        for post in posts
        if post.get(metric) is not None
        and (post.get("recipients") is None or int(post["recipients"]) > 0)
    ]


def _rank(posts: list[dict[str, Any]], metric: str) -> tuple[dict[str, Any], dict[str, Any]]:
    comparable = _eligible(posts, metric)
    if not comparable:
        return {}, {}
    return (
        max(comparable, key=lambda post: float(post[metric])),
        min(comparable, key=lambda post: float(post[metric])),
    )


def _snapshot(data: dict[str, Any], run_id: str) -> dict[str, Any]:
    latest = (data.get("recent_posts") or [{}])[0] if data.get("recent_posts") else {}
    return {
        "run_id": run_id,
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "publication_id": data.get("publication_id"),
        "active_subscribers": data.get("active_subscribers"),
        "total_subscribers": data.get("total_subscribers"),
        "avg_open_rate": data.get("avg_open_rate"),
        "avg_click_rate": data.get("avg_click_rate"),
        "latest_post": {
            key: latest.get(key)
            for key in ("id", "title", "published", "recipients", "open_rate", "click_rate")
        },
    }


def _state_path(workspace: str) -> Path:
    return ensure_workspace(workspace) / "Work" / "state" / _STATE_FILE


def _load_previous_snapshot(workspace: str, run_id: str) -> dict[str, Any] | None:
    path = _state_path(workspace)
    if not path.exists():
        return None
    try:
        state = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("Newsletter Intelligence history is unreadable") from error
    if not isinstance(state, dict) or not isinstance(state.get("current"), dict):
        raise RuntimeError("Newsletter Intelligence history is invalid")
    if state["current"].get("run_id") == run_id:
        previous = state.get("previous")
        return previous if isinstance(previous, dict) else None
    return state["current"]


def _save_snapshot(
    workspace: str,
    current: dict[str, Any],
    previous: dict[str, Any] | None,
) -> None:
    path = _state_path(workspace)
    state = {"current": current, "previous": previous}
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2, default=str))
    temporary.replace(path)


def _change_sentence(label: str, current: Any, prior: Any, *, rate: bool = False) -> str:
    if current is None or prior is None:
        return f"{label}: no prior comparable value is available yet."
    difference = float(current) - float(prior)
    if difference == 0:
        return f"{label}: unchanged at {_pct(current) if rate else _count(current)}."
    direction = "up" if difference > 0 else "down"
    amount = f"{abs(difference):.1%}" if rate else f"{abs(int(difference)):,}"
    current_text = _pct(current) if rate else _count(current)
    return f"{label}: {direction} {amount} to {current_text}."


def _derive(
    data: dict[str, Any], previous_snapshot: dict[str, Any] | None = None
) -> dict[str, Any]:
    posts = [post for post in data.get("recent_posts", []) if isinstance(post, dict)]
    latest = posts[0] if posts else {}
    previous_post = posts[1] if len(posts) > 1 else {}
    prior_posts = posts[1:]
    best_open, weakest_open = _rank(posts, "open_rate")
    best_click, weakest_click = _rank(posts, "click_rate")

    recent_open_baseline = _mean(prior_posts, "open_rate")
    recent_click_baseline = _mean(prior_posts, "click_rate")
    open_baseline = recent_open_baseline if recent_open_baseline is not None else data.get("avg_open_rate")
    click_baseline = recent_click_baseline if recent_click_baseline is not None else data.get("avg_click_rate")
    open_baseline_label = "prior recent sends" if recent_open_baseline is not None else "publication baseline"
    click_baseline_label = "prior recent sends" if recent_click_baseline is not None else "publication baseline"
    open_delta, open_label = _delta(latest.get("open_rate"), open_baseline)
    click_delta, click_label = _delta(latest.get("click_rate"), click_baseline)

    prior_latest = (previous_snapshot or {}).get("latest_post") or {}
    what_changed: list[str] = []
    if previous_snapshot is None:
        what_changed.append("This is Harbor’s first saved snapshot; subscriber movement will be available after the next run.")
    else:
        if latest and latest.get("id") == prior_latest.get("id"):
            what_changed.append("No new issue has appeared since the prior Harbor snapshot; engagement may still be accumulating.")
        elif latest:
            what_changed.append(f"A new latest issue is available: **{latest.get('title') or 'Untitled'}**.")
        what_changed.extend([
            _change_sentence("Active subscribers", data.get("active_subscribers"), previous_snapshot.get("active_subscribers")),
            _change_sentence("Publication average open rate", data.get("avg_open_rate"), previous_snapshot.get("avg_open_rate"), rate=True),
            _change_sentence("Publication average click rate", data.get("avg_click_rate"), previous_snapshot.get("avg_click_rate"), rate=True),
        ])

    trends: list[dict[str, Any]] = []
    for label, current, baseline, difference, relation, source in (
        ("Open rate", latest.get("open_rate"), open_baseline, open_delta, open_label, open_baseline_label),
        ("Click rate", latest.get("click_rate"), click_baseline, click_delta, click_label, click_baseline_label),
    ):
        trends.append({"metric": label, "current": current, "baseline": baseline, "delta": difference, "relation": relation, "baseline_label": source})

    audience_signals = [f"Active subscribers: **{_count(data.get('active_subscribers'))}**."]
    if previous_snapshot is None:
        audience_signals.append("Growth since prior Harbor snapshot: not available on the first run.")
    else:
        audience_signals.append(_change_sentence("Growth since prior Harbor snapshot", data.get("active_subscribers"), previous_snapshot.get("active_subscribers")))
    free = data.get("active_free_subscribers")
    premium = data.get("active_premium_subscribers")
    if free is not None or premium is not None:
        audience_signals.append(f"Audience mix: {_count(free)} free and {_count(premium)} premium active subscribers.")

    anomalies: list[str] = []
    if not posts:
        anomalies.append("No published issues were returned, so content performance cannot be assessed.")
    if data.get("active_subscribers") == 0:
        anomalies.append("The publication reports zero active subscribers.")
    if latest:
        recipients = latest.get("recipients")
        delivered = latest.get("delivered")
        if recipients == 0:
            anomalies.append("The latest issue reports zero email recipients.")
        if recipients and delivered is not None and delivered / recipients < 0.98:
            anomalies.append(f"Latest-issue delivery was {delivered / recipients:.1%}, below Harbor’s 98% watch threshold.")
        if recipients and latest.get("unsubscribes") is not None:
            unsubscribe_rate = latest["unsubscribes"] / recipients
            if unsubscribe_rate >= 0.01:
                anomalies.append(f"Latest-issue unsubscribes were {unsubscribe_rate:.1%}, at or above Harbor’s 1% watch threshold.")
        if latest.get("spam_reports"):
            anomalies.append(f"The latest issue recorded {_count(latest['spam_reports'])} spam report(s).")
    if open_delta is not None and abs(open_delta) >= 0.10:
        anomalies.append(f"Latest open rate moved {abs(open_delta):.1%} {'above' if open_delta > 0 else 'below'} its comparison baseline.")
    if click_delta is not None and abs(click_delta) >= 0.03:
        anomalies.append(f"Latest click rate moved {abs(click_delta):.1%} {'above' if click_delta > 0 else 'below'} its comparison baseline.")

    why_it_matters: list[str] = []
    if open_delta is None:
        why_it_matters.append("Open performance cannot yet be compared reliably; more sends are needed.")
    elif open_delta >= 0.01:
        why_it_matters.append("The latest packaging is earning materially more opens than comparable sends.")
    elif open_delta <= -0.01:
        why_it_matters.append("The latest subject-line or sender framing is attracting fewer opens than comparable sends.")
    else:
        why_it_matters.append("Open performance is stable, so a controlled test is more useful than a broad change.")
    if click_delta is None:
        why_it_matters.append("Click intent cannot yet be compared reliably.")
    elif click_delta >= 0.005:
        why_it_matters.append("Readers are acting on the latest issue at a stronger rate than comparable sends.")
    elif click_delta <= -0.005:
        why_it_matters.append("Reader action is lagging, pointing to CTA, offer, or content-intent friction.")
    else:
        why_it_matters.append("Click performance is near its comparison level; preserve the control while testing one CTA variable.")

    recommendations: list[str] = []
    if not latest:
        recommendations.append("Publish an issue before evaluating content performance.")
    else:
        if latest.get("recipients") == 0:
            recommendations.append("Confirm the next issue is sent to an active subscriber audience.")
        if open_delta is not None and open_delta >= 0.01:
            recommendations.append("Reuse the latest issue’s subject-line structure as the control for the next send.")
        elif open_delta is not None and open_delta <= -0.01:
            recommendations.append("Test one clearly different subject-line angle on the next send.")
        elif open_delta is not None:
            recommendations.append("Keep the subject-line approach stable and test only one packaging variable next.")
        if click_delta is not None and click_delta >= 0.005:
            recommendations.append("Preserve the latest CTA placement and link hierarchy as the next-send control.")
        elif click_delta is not None and click_delta <= -0.005:
            recommendations.append("Reduce competing links and move the primary CTA earlier in the next issue.")
        if best_open and best_open.get("id") != latest.get("id"):
            recommendations.append(f"Use **{best_open.get('title') or 'the strongest opener'}** as a reference for future subject and topic framing.")
        if best_click and best_click.get("id") != latest.get("id"):
            recommendations.append(f"Review **{best_click.get('title') or 'the strongest click performer'}** for repeatable CTA and offer patterns.")
    if data.get("active_subscribers") == 0:
        recommendations.insert(0, "Build an initial active subscriber cohort before treating engagement rates as decision-grade.")

    headline = anomalies[0] if anomalies else why_it_matters[0] if why_it_matters else "Harbor collected the latest available newsletter performance."
    return {
        "headline": headline,
        "latest": latest,
        "previous_post": previous_post,
        "best_open": best_open,
        "weakest_open": weakest_open,
        "best_click": best_click,
        "weakest_click": weakest_click,
        "what_changed": what_changed,
        "why_it_matters": why_it_matters,
        "trends": trends,
        "audience_signals": audience_signals,
        "recommendations": recommendations[:5],
        "anomalies": anomalies,
    }


def _trend_line(trend: dict[str, Any]) -> str:
    if trend["current"] is None or trend["baseline"] is None:
        return f"{trend['metric']}: comparison unavailable because the baseline is zero or unavailable."
    if trend["delta"] is None:
        return f"{trend['metric']}: comparison unavailable because the baseline is zero or unavailable."
    return f"{trend['metric']}: **{_pct(trend['current'])}**, {trend['relation']} {trend['baseline_label']} of {_pct(trend['baseline'])} ({trend['delta']:+.1%})."


def _content_lines(derived: dict[str, Any]) -> list[str]:
    comparable_ids = {
        str(post.get("id") or post.get("title"))
        for post in (derived["best_open"], derived["weakest_open"])
        if post
    }
    if len(comparable_ids) < 2:
        return ["At least two recipient-backed issues are needed to rank strongest and weakest content."]
    lines: list[str] = []
    for label, post, metric in (
        ("Strongest opener", derived["best_open"], "open_rate"),
        ("Weakest opener", derived["weakest_open"], "open_rate"),
        ("Strongest click performer", derived["best_click"], "click_rate"),
        ("Weakest click performer", derived["weakest_click"], "click_rate"),
    ):
        if post:
            lines.append(f"{label}: **{post.get('title') or 'Untitled'}** at {_pct(post.get(metric))}.")
    return lines or ["Not enough recipient-backed post data is available to rank content."]


def _markdown(tenant: TenantConfig, data: dict[str, Any], derived: dict[str, Any]) -> str:
    try:
        local_now = dt.datetime.now(dt.timezone.utc).astimezone(ZoneInfo(tenant.timezone))
    except ZoneInfoNotFoundError:
        local_now = dt.datetime.now(dt.timezone.utc)
    today = local_now.date().strftime("%A, %B %d, %Y")
    anomalies = derived["anomalies"] or ["No material anomaly crossed Harbor’s current evidence-based thresholds."]
    lines = [
        f"# Harbor Newsletter Intelligence — {today}",
        "",
        f"**{data.get('publication_name') or tenant.name}**",
        "",
    ]
    if data.get("_mock"):
        lines += ["> Development mode: this report uses explicitly requested mock data.", ""]
    lines += [
        f"**Today’s signal:** {derived['headline']}",
        "",
        "## What changed",
        *[f"- {item}" for item in derived["what_changed"]],
        "",
        "## Why it matters",
        *[f"- {item}" for item in derived["why_it_matters"]],
        "",
        "## Trends vs prior performance / baseline",
        *[f"- {_trend_line(item)}" for item in derived["trends"]],
        "",
        "## Strongest and weakest content",
        *[f"- {item}" for item in _content_lines(derived)],
        "",
        "## Audience and growth signals",
        *[f"- {item}" for item in derived["audience_signals"]],
        "",
        "## Recommended actions",
        *[f"- {item}" for item in derived["recommendations"]],
        "",
        "## Important anomalies",
        *[f"- {item}" for item in anomalies],
        "",
        "---",
        (
            f"Source: explicitly requested beehiiv mock data for publication {data.get('publication_id') or 'unknown'}."
            if data.get("_mock")
            else f"Source: live beehiiv data retrieved for publication {data.get('publication_id') or 'unknown'}."
        ),
        "Harbor · Newsletter Intelligence",
    ]
    return "\n".join(lines) + "\n"


class NewsletterIntelligenceWorker:
    id = "newsletter-intelligence"
    label = "Newsletter Intelligence"

    def run(self, tenant: TenantConfig, inputs: dict[str, Any] | None = None) -> WorkerResult:
        inputs = inputs or {}
        if not tenant.worker_enabled(self.id):
            return WorkerResult(self.id, "disabled", "Worker is not enabled for this tenant.")

        conn = tenant.connection("beehiiv")
        auth_mode = conn.settings.get("auth_mode", "bearer")
        api_key = resolve(conn.secret_ref, required=False) if auth_mode == "bearer" else None
        publication_id = inputs.get("publication_id") or conn.settings.get("publication_id")
        if not publication_id:
            return WorkerResult(self.id, "failed", "beehiiv publication_id is missing")

        run_id = inputs.get("_harbor_run_id") or f"run_{dt.datetime.now(dt.timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
        recent_posts = int(inputs.get("recent_posts") or conn.settings.get("recent_posts", 10))
        base_url = conn.settings.get("gateway_base_url") or conn.settings.get("base_url")
        allow_mock = str(inputs.get("mode", "")).lower() == "mock"
        data = beehiiv_client.publication_performance(
            publication_id,
            recent_posts,
            api_key=api_key,
            base_url=base_url,
            auth_mode=auth_mode,
            allow_mock=allow_mock,
        )
        previous_snapshot = _load_previous_snapshot(tenant.workspace, run_id)
        derived = _derive(data, previous_snapshot)
        report = _markdown(tenant, data, derived)
        report_path = write_report(tenant.workspace, "newsletter-intelligence", report, artifact_id=run_id)
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
            "intelligence": derived,
        }
        run_path = write_run(tenant.workspace, run_record, run_id)
        _save_snapshot(tenant.workspace, _snapshot(data, run_id), previous_snapshot)
        warnings = []
        if data.get("_mock"):
            warnings.append("Explicit development mock mode was requested; no production run should contain mock data.")
        return WorkerResult(
            worker_id=self.id,
            status="completed",
            summary=derived["headline"],
            data={"metrics": data, "derived": derived, "intelligence": derived, "run_record": run_path},
            deliverables=[report_path],
            warnings=warnings,
        )


WORKER = register(NewsletterIntelligenceWorker())
