import datetime as dt

import pytest

from harbor.config import ConnectionConfig
from harbor.connectors.base import NewsletterRequest
from harbor.connectors.beehiiv import BeehiivNewsletterConnector
from harbor.newsletter_model import (
    DateWindow,
    MetricState,
    MetricValue,
    provider_metric,
)


def test_metric_contract_distinguishes_zero_from_missing_and_unsupported():
    zero = provider_metric(0, provider="Beehiiv")
    missing = provider_metric(None, provider="Beehiiv")
    unsupported = provider_metric(None, provider="Kit", supported=False)
    history = MetricValue.insufficient_history()

    assert zero.to_dict() == {"value": 0, "state": "available", "detail": None}
    assert missing.state is MetricState.NO_DATA
    assert missing.value is None
    assert unsupported.to_dict() == {
        "value": None,
        "state": "not_supported",
        "detail": "Not available from Kit",
    }
    assert history.state is MetricState.INSUFFICIENT_HISTORY
    assert history.detail == "Insufficient history"


def test_metric_contract_rejects_values_on_unavailable_states():
    with pytest.raises(ValueError, match="unavailable metrics"):
        MetricValue(value=0, state=MetricState.NO_DATA)


def test_date_window_requires_ordered_timezone_aware_bounds():
    with pytest.raises(ValueError, match="timezone-aware"):
        DateWindow(start=dt.datetime(2026, 9, 1), label="custom")  # noqa: DTZ001
    with pytest.raises(ValueError, match="start must be before end"):
        DateWindow(
            start=dt.datetime(2026, 9, 2, tzinfo=dt.timezone.utc),
            end=dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc),
            label="custom",
        )


def test_beehiiv_adapter_maps_provider_shape_to_normalized_contract(monkeypatch):
    monkeypatch.setattr(
        "harbor.connectors.beehiiv.beehiiv_client.publication_performance",
        lambda *args, **kwargs: {
            "publication_id": "pub_one",
            "publication_name": "Signal Weekly",
            "active_subscribers": 0,
            "active_free_subscribers": None,
            "active_premium_subscribers": None,
            "total_subscribers": None,
            "total_sent": 4,
            "avg_open_rate": 0.45,
            "avg_click_rate": None,
            "recent_posts": [
                {
                    "id": "post_one",
                    "title": "Visible title",
                    "subject_line": "A real subject line",
                    "published": "2026-09-09T12:00:00Z",
                    "audience": "free",
                    "content_tags": ["growth"],
                    "recipients": 0,
                    "delivered": None,
                    "opens": 0,
                    "unique_opens": None,
                    "open_rate": 0.0,
                    "clicks": 0,
                    "unique_clicks": None,
                    "click_rate": 0.0,
                    "unsubscribes": None,
                    "spam_reports": None,
                    "web_views": 0,
                    "web_clicks": None,
                }
            ],
        },
    )
    connector = BeehiivNewsletterConnector()
    connection = ConnectionConfig(
        id="bee-one",
        provider="beehiiv",
        settings={"auth_mode": "sprite_connector", "publication_id": "pub_one"},
    )

    result = connector.sync(
        connection,
        NewsletterRequest(window=DateWindow(label="latest"), issue_limit=10),
    )

    publication = result.publications[0]
    issue = publication.issues[0]
    assert publication.subscribers.value == 0
    assert publication.subscribers.state is MetricState.AVAILABLE
    assert publication.free_subscribers.state is MetricState.NO_DATA
    assert publication.average_click_rate.state is MetricState.NO_DATA
    assert issue.subject_line == "A real subject line"
    assert issue.tags == ("growth",)
    assert issue.open_rate.value == 0.0
    assert issue.delivered.state is MetricState.NO_DATA
    assert issue.unsubscribe_rate.state is MetricState.NO_DATA
    serialized = result.to_dict()
    assert serialized["schema_version"] == 1
    assert serialized["publications"][0]["metrics"]["subscribers"]["value"] == 0
    assert (
        serialized["publications"][0]["metrics"]["free_subscribers"]["state"]
        == "no_data"
    )
