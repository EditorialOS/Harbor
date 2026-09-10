import datetime as dt

import pytest

from harbor.time_ranges import comparison_window, resolve_date_window

NOW = dt.datetime(2026, 9, 10, 20, 30, tzinfo=dt.timezone.utc)


@pytest.mark.parametrize(
    ("name", "expected_start"),
    [
        ("today", "2026-09-10T07:00:00+00:00"),
        ("yesterday", "2026-09-09T07:00:00+00:00"),
        ("last 7 days", "2026-09-03T20:30:00+00:00"),
        ("this week", "2026-09-07T07:00:00+00:00"),
        ("month", "2026-09-01T07:00:00+00:00"),
        ("last 30 days", "2026-08-11T20:30:00+00:00"),
        ("quarter", "2026-07-01T07:00:00+00:00"),
        ("last 90 days", "2026-06-12T20:30:00+00:00"),
        ("six months", "2026-03-10T20:30:00+00:00"),
        ("YTD", "2026-01-01T08:00:00+00:00"),
        ("previous year", "2025-01-01T08:00:00+00:00"),
    ],
)
def test_resolves_supported_timeframes(name, expected_start):
    window = resolve_date_window(
        name, timezone="America/Los_Angeles", now=NOW
    )
    assert window.start.isoformat() == expected_start


def test_custom_dates_are_inclusive_in_customer_timezone():
    window = resolve_date_window(
        "custom",
        timezone="America/Los_Angeles",
        start_date="2026-09-01",
        end_date="2026-09-03",
        now=NOW,
    )
    assert window.start.isoformat() == "2026-09-01T07:00:00+00:00"
    assert window.end.isoformat() == "2026-09-04T07:00:00+00:00"


def test_prior_period_and_ytd_comparison_windows():
    current = resolve_date_window(
        "last 7 days", timezone="America/Los_Angeles", now=NOW
    )
    prior = comparison_window(current)
    assert prior.end == current.start
    assert prior.end - prior.start == current.end - current.start

    ytd = resolve_date_window("ytd", timezone="America/Los_Angeles", now=NOW)
    prior_ytd = comparison_window(ytd)
    assert prior_ytd.label == "same_period_last_year"
    assert prior_ytd.start.year == 2025
    assert prior_ytd.end.year == 2025


def test_custom_range_validation_is_visible():
    with pytest.raises(ValueError, match="requires start_date and end_date"):
        resolve_date_window("custom", timezone="UTC", start_date="2026-01-01")
    with pytest.raises(ValueError, match="start_date must be"):
        resolve_date_window(
            "custom",
            timezone="UTC",
            start_date="2026-02-01",
            end_date="2026-01-01",
        )
