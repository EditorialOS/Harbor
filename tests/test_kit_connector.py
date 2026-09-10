import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from harbor import kit_client
from harbor.config import ConnectionConfig, load_tenant
from harbor.connectors.base import NewsletterRequest
from harbor.connectors.kit import KitNewsletterConnector
from harbor.newsletter_model import DateWindow, MetricState
from harbor.runtime import run_worker


def _responses():
    return {
        "/v4/account": {
            "account": {
                "id": 29,
                "name": "Kit Signal",
                "timezone": {"name": "America/Los_Angeles"},
            }
        },
        "/v4/subscribers": {
            "subscribers": [],
            "pagination": {"total_count": 0, "has_next_page": False},
        },
        "/v4/broadcasts/stats": {
            "broadcasts": [
                {
                    "id": 205,
                    "subject": "The clear signal",
                    "send_at": "2026-09-09T13:00:00Z",
                    "stats": {
                        "recipients": 0,
                        "open_rate": 0,
                        "emails_opened": 0,
                        "click_rate": 0,
                        "unsubscribe_rate": 0,
                        "unsubscribes": 0,
                        "total_clicks": 0,
                        "status": "completed",
                        "open_tracking_disabled": False,
                        "click_tracking_disabled": False,
                    },
                }
            ],
            "pagination": {
                "total_count": 1,
                "has_next_page": False,
                "end_cursor": "cursor-one",
            },
        },
        "/v4/tags": {
            "tags": [{"id": 8, "name": "VIP", "subscriber_count": 0}],
            "pagination": {"has_next_page": False},
        },
    }


def test_kit_v4_shape_through_sprite_connector(monkeypatch):
    responses = _responses()
    requests = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(self.payload).encode()

    def urlopen(request, timeout):
        requests.append(request)
        path = urlsplit(request.full_url).path
        provider_path = path[path.index("/v4/") :]
        return Response(responses[provider_path])

    monkeypatch.setattr(kit_client.urllib.request, "urlopen", urlopen)
    connection = ConnectionConfig(
        id="kit-main",
        provider="kit",
        settings={
            "auth_mode": "sprite_connector",
            "gateway_base_url": "https://api.sprites.dev/v1/gateway/custom_api/kit-main/v4",
            "publication_id": "29",
        },
    )

    result = KitNewsletterConnector().sync(
        connection, NewsletterRequest(window=DateWindow(label="latest"), issue_limit=10)
    )

    publication = result.publications[0]
    issue = publication.issues[0]
    assert publication.provider_id == "29"
    assert publication.subscribers.value == 0
    assert publication.subscribers.state is MetricState.AVAILABLE
    assert publication.free_subscribers.state is MetricState.NOT_SUPPORTED
    assert publication.subscriber_growth.state is MetricState.INSUFFICIENT_HISTORY
    assert publication.segments == (
        {"provider_id": "8", "name": "VIP", "subscriber_count": 0},
    )
    assert issue.subject_line == "The clear signal"
    assert issue.open_rate.value == 0.0
    assert issue.click_rate.value == 0.0
    assert issue.delivered.state is MetricState.NOT_SUPPORTED
    assert issue.unique_opens.state is MetricState.NOT_SUPPORTED
    assert issue.spam_reports.detail == "Not available from Kit"
    assert all(request.get_header("Authorization") is None for request in requests)
    assert all(request.get_header("X-kit-api-key") is None for request in requests)
    broadcast_request = next(
        request for request in requests if "/broadcasts/stats" in request.full_url
    )
    query = parse_qs(urlsplit(broadcast_request.full_url).query)
    assert query["status"] == ["completed"]
    assert query["include_total_count"] == ["true"]


def test_kit_tracking_disabled_is_not_rendered_as_zero():
    issue = KitNewsletterConnector._issue(
        {
            "id": 1,
            "subject": "Tracking off",
            "stats": {
                "open_tracking_disabled": True,
                "click_tracking_disabled": True,
                "open_rate": 0,
                "click_rate": 0,
                "emails_opened": 0,
                "total_clicks": 0,
                "recipients": 12,
                "unsubscribes": None,
                "unsubscribe_rate": None,
            },
        }
    )

    assert issue.open_rate.state is MetricState.NOT_SUPPORTED
    assert issue.opens.state is MetricState.NOT_SUPPORTED
    assert issue.click_rate.state is MetricState.NOT_SUPPORTED
    assert issue.clicks.state is MetricState.NOT_SUPPORTED
    assert issue.recipients.value == 12


def test_kit_client_uses_documented_api_key_header_only_in_explicit_mode(monkeypatch):
    captured = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b'{"account":{"id":1,"name":"Test","timezone":{}}}'

    def urlopen(request, timeout):
        captured.append(request)
        return Response()

    monkeypatch.setattr(kit_client.urllib.request, "urlopen", urlopen)
    kit_client.current_account(credential="test-only", auth_mode="api_key")

    assert captured[0].get_header("X-kit-api-key") == "test-only"
    assert captured[0].get_header("Authorization") is None


def test_same_worker_runs_kit_without_provider_specific_intelligence(
    tmp_path, monkeypatch
):
    responses = _responses()
    monkeypatch.setattr(
        kit_client,
        "_get",
        lambda path, params=None, **kwargs: responses[f"/v4{path}"],
    )
    config = tmp_path / "tenant.json"
    config.write_text(
        json.dumps(
            {
                "tenant_id": "kit-tenant",
                "name": "Kit Tenant",
                "workspace": "workspace",
                "workers": ["newsletter-intelligence"],
                "connections": [
                    {
                        "id": "kit-main",
                        "provider": "kit",
                        "settings": {
                            "auth_mode": "sprite_connector",
                            "publication_id": "29",
                        },
                    }
                ],
            }
        )
    )

    result = run_worker(
        load_tenant(config),
        "newsletter-intelligence",
        {"_harbor_run_id": "run_kit_normalized"},
    )

    assert result.status == "completed"
    assert result.data["newsletter_data"]["publications"][0]["provider"] == "kit"
    report = Path(result.deliverables[0]).read_text()
    assert "Source: live kit data" in report
    assert "zero active subscribers" in report
