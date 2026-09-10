"""Provider-neutral newsletter data contracts.

Connectors translate provider responses into these immutable values. Newsletter
workers consume this module and never need to understand provider response
shapes. Metric state is explicit so a reported zero cannot be confused with a
missing, unsupported, or not-yet-comparable value.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MetricState(str, Enum):
    AVAILABLE = "available"
    NO_DATA = "no_data"
    NOT_SUPPORTED = "not_supported"
    INSUFFICIENT_HISTORY = "insufficient_history"


Numeric = int | float


@dataclass(frozen=True)
class MetricValue:
    value: Numeric | None
    state: MetricState
    detail: str | None = None

    def __post_init__(self) -> None:
        if self.state is MetricState.AVAILABLE:
            if self.value is None or isinstance(self.value, bool):
                raise ValueError("available metrics require a numeric value")
        elif self.value is not None:
            raise ValueError("unavailable metrics cannot carry a value")

    @classmethod
    def available(cls, value: Numeric) -> MetricValue:
        return cls(value=value, state=MetricState.AVAILABLE)

    @classmethod
    def no_data(cls, detail: str | None = None) -> MetricValue:
        return cls(value=None, state=MetricState.NO_DATA, detail=detail)

    @classmethod
    def not_supported(cls, provider: str) -> MetricValue:
        return cls(
            value=None,
            state=MetricState.NOT_SUPPORTED,
            detail=f"Not available from {provider}",
        )

    @classmethod
    def insufficient_history(cls, detail: str | None = None) -> MetricValue:
        return cls(
            value=None,
            state=MetricState.INSUFFICIENT_HISTORY,
            detail=detail or "Insufficient history",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "state": self.state.value,
            "detail": self.detail,
        }


def provider_metric(
    value: Any,
    *,
    provider: str,
    supported: bool = True,
    rate: bool = False,
) -> MetricValue:
    """Create a metric from a provider field without inventing a zero."""
    if not supported:
        return MetricValue.not_supported(provider)
    if value is None:
        return MetricValue.no_data(f"No data returned by {provider}")
    if isinstance(value, bool):
        raise TypeError("metric values cannot be booleans")
    try:
        number: Numeric = float(value) if rate else int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{provider} returned a non-numeric metric") from error
    return MetricValue.available(number)


@dataclass(frozen=True)
class DateWindow:
    start: dt.datetime | None = None
    end: dt.datetime | None = None
    label: str = "latest"

    def __post_init__(self) -> None:
        for value in (self.start, self.end):
            if value is not None and value.tzinfo is None:
                raise ValueError("date windows must use timezone-aware datetimes")
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise ValueError("date window start must be before end")

    def to_dict(self) -> dict[str, str | None]:
        return {
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "label": self.label,
        }


def _empty_metric() -> MetricValue:
    return MetricValue.no_data()


@dataclass(frozen=True)
class NewsletterIssue:
    provider_id: str | None
    title: str | None
    subject_line: str | None
    sent_at: str | None
    audience: str | None = None
    tags: tuple[str, ...] = ()
    recipients: MetricValue = field(default_factory=_empty_metric)
    delivered: MetricValue = field(default_factory=_empty_metric)
    opens: MetricValue = field(default_factory=_empty_metric)
    unique_opens: MetricValue = field(default_factory=_empty_metric)
    open_rate: MetricValue = field(default_factory=_empty_metric)
    clicks: MetricValue = field(default_factory=_empty_metric)
    unique_clicks: MetricValue = field(default_factory=_empty_metric)
    click_rate: MetricValue = field(default_factory=_empty_metric)
    unsubscribes: MetricValue = field(default_factory=_empty_metric)
    unsubscribe_rate: MetricValue = field(default_factory=_empty_metric)
    spam_reports: MetricValue = field(default_factory=_empty_metric)
    web_views: MetricValue = field(default_factory=_empty_metric)
    web_clicks: MetricValue = field(default_factory=_empty_metric)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "title": self.title,
            "subject_line": self.subject_line,
            "sent_at": self.sent_at,
            "audience": self.audience,
            "tags": list(self.tags),
            "metrics": {
                name: getattr(self, name).to_dict()
                for name in (
                    "recipients",
                    "delivered",
                    "opens",
                    "unique_opens",
                    "open_rate",
                    "clicks",
                    "unique_clicks",
                    "click_rate",
                    "unsubscribes",
                    "unsubscribe_rate",
                    "spam_reports",
                    "web_views",
                    "web_clicks",
                )
            },
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class NewsletterPublication:
    provider: str
    connection_id: str
    provider_id: str
    name: str | None
    subscribers: MetricValue = field(default_factory=_empty_metric)
    free_subscribers: MetricValue = field(default_factory=_empty_metric)
    paid_subscribers: MetricValue = field(default_factory=_empty_metric)
    total_subscribers: MetricValue = field(default_factory=_empty_metric)
    subscriber_growth: MetricValue = field(default_factory=_empty_metric)
    sends: MetricValue = field(default_factory=_empty_metric)
    average_open_rate: MetricValue = field(default_factory=_empty_metric)
    average_click_rate: MetricValue = field(default_factory=_empty_metric)
    issues: tuple[NewsletterIssue, ...] = ()
    segments: tuple[dict[str, Any], ...] = ()
    growth_attribution: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "connection_id": self.connection_id,
            "provider_id": self.provider_id,
            "name": self.name,
            "metrics": {
                name: getattr(self, name).to_dict()
                for name in (
                    "subscribers",
                    "free_subscribers",
                    "paid_subscribers",
                    "total_subscribers",
                    "subscriber_growth",
                    "sends",
                    "average_open_rate",
                    "average_click_rate",
                )
            },
            "issues": [issue.to_dict() for issue in self.issues],
            "segments": list(self.segments),
            "growth_attribution": list(self.growth_attribution),
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class NewsletterDataset:
    window: DateWindow
    publications: tuple[NewsletterPublication, ...]
    capabilities: tuple[str, ...]
    captured_at: str
    warnings: tuple[str, ...] = ()
    mock: bool = False
    schema_version: int = 1

    def __post_init__(self) -> None:
        identities = [
            (publication.connection_id, publication.provider_id)
            for publication in self.publications
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("newsletter dataset contains duplicate publications")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "window": self.window.to_dict(),
            "captured_at": self.captured_at,
            "capabilities": list(self.capabilities),
            "publications": [item.to_dict() for item in self.publications],
            "warnings": list(self.warnings),
            "mock": self.mock,
        }
