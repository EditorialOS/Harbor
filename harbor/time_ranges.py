"""Resolve customer-facing timeframe names into explicit UTC date windows."""

from __future__ import annotations

import calendar
import datetime as dt
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .newsletter_model import DateWindow

SUPPORTED_TIMEFRAMES = (
    "today",
    "yesterday",
    "last_7_days",
    "week",
    "month",
    "last_30_days",
    "quarter",
    "last_90_days",
    "six_months",
    "ytd",
    "previous_year",
    "custom",
)

_ALIASES = {
    "7d": "last_7_days",
    "last 7 days": "last_7_days",
    "this week": "week",
    "this month": "month",
    "30d": "last_30_days",
    "last 30 days": "last_30_days",
    "qtr": "quarter",
    "this quarter": "quarter",
    "90d": "last_90_days",
    "last 90 days": "last_90_days",
    "6m": "six_months",
    "six months": "six_months",
    "last six months": "six_months",
    "year to date": "ytd",
    "last year": "previous_year",
}


def canonical_timeframe(value: str | None) -> str:
    words = " ".join((value or "today").strip().lower().replace("-", " ").replace("_", " ").split())
    normalized = _ALIASES.get(words, words.replace(" ", "_"))
    if normalized not in SUPPORTED_TIMEFRAMES:
        raise ValueError(
            f"unsupported timeframe '{value}'; use {', '.join(SUPPORTED_TIMEFRAMES)}"
        )
    return normalized


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"unknown timezone '{name}'") from error


def _parse_date(value: str, label: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must use YYYY-MM-DD") from error


def _month_shift(value: dt.datetime, months: int) -> dt.datetime:
    index = value.year * 12 + value.month - 1 + months
    year, month_index = divmod(index, 12)
    month = month_index + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def resolve_date_window(
    timeframe: str | None,
    *,
    timezone: str,
    start_date: str | None = None,
    end_date: str | None = None,
    now: dt.datetime | None = None,
) -> DateWindow:
    """Resolve a named range; the returned end is exclusive."""
    label = canonical_timeframe(timeframe)
    zone = _timezone(timezone)
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local_now = current.astimezone(zone)
    today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)

    if label == "custom":
        if not start_date or not end_date:
            raise ValueError("custom timeframe requires start_date and end_date")
        start_day = _parse_date(start_date, "start_date")
        end_day = _parse_date(end_date, "end_date")
        if start_day > end_day:
            raise ValueError("start_date must be on or before end_date")
        start = dt.datetime.combine(start_day, dt.time.min, zone)
        end = dt.datetime.combine(end_day + dt.timedelta(days=1), dt.time.min, zone)
    elif label == "today":
        start, end = today, local_now
    elif label == "yesterday":
        start, end = today - dt.timedelta(days=1), today
    elif label == "last_7_days":
        start, end = local_now - dt.timedelta(days=7), local_now
    elif label == "week":
        start, end = today - dt.timedelta(days=today.weekday()), local_now
    elif label == "month":
        start, end = today.replace(day=1), local_now
    elif label == "last_30_days":
        start, end = local_now - dt.timedelta(days=30), local_now
    elif label == "quarter":
        quarter_month = ((today.month - 1) // 3) * 3 + 1
        start, end = today.replace(month=quarter_month, day=1), local_now
    elif label == "last_90_days":
        start, end = local_now - dt.timedelta(days=90), local_now
    elif label == "six_months":
        start, end = _month_shift(local_now, -6), local_now
    elif label == "ytd":
        start, end = today.replace(month=1, day=1), local_now
    else:
        start = today.replace(year=today.year - 1, month=1, day=1)
        end = today.replace(month=1, day=1)

    return DateWindow(
        start=start.astimezone(dt.timezone.utc),
        end=end.astimezone(dt.timezone.utc),
        label=label,
    )


def comparison_window(window: DateWindow) -> DateWindow:
    if window.start is None or window.end is None:
        raise ValueError("comparison requires a bounded date window")
    if window.label == "ytd":
        try:
            start = window.start.replace(year=window.start.year - 1)
            end = window.end.replace(year=window.end.year - 1)
        except ValueError:
            start = window.start.replace(year=window.start.year - 1, day=28)
            end = window.end.replace(year=window.end.year - 1, day=28)
        return DateWindow(start=start, end=end, label="same_period_last_year")
    duration = window.end - window.start
    return DateWindow(
        start=window.start - duration,
        end=window.start,
        label=f"prior_{window.label}",
    )
