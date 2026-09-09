import json
from pathlib import Path

from harbor import beehiiv_client


def test_sanitized_live_shape_through_sprite_connector(monkeypatch):
    fixture_path = Path(__file__).parent / "fixtures" / "beehiiv_live_shape_sanitized.json"
    fixture = json.loads(fixture_path.read_text())
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
        payload = fixture["posts"] if "/posts?" in request.full_url else fixture["publication"]
        return Response(payload)

    monkeypatch.setattr(beehiiv_client.urllib.request, "urlopen", urlopen)
    result = beehiiv_client.publication_performance(
        "pub_sanitized",
        base_url="https://api.sprites.dev/v1/gateway/custom_api/connector",
        auth_mode="sprite_connector",
    )

    assert result["publication_name"] == "Sanitized publication"
    assert result["active_subscribers"] == 0
    assert result["recent_posts"][0] == {
        "id": "post_sanitized",
        "title": "Sanitized issue",
        "published": "2026-09-05T12:00:00Z",
        "recipients": 0,
        "delivered": None,
        "open_rate": 0.0,
        "click_rate": 0.0,
        "opens": 0,
        "unique_opens": None,
        "clicks": 0,
        "unique_clicks": None,
        "unsubscribes": None,
        "spam_reports": None,
        "web_views": 0,
        "web_clicks": None,
        "upgrades": None,
    }
    assert len(requests) == 2
    assert all(request.get_header("Authorization") is None for request in requests)


def test_percentage_shaped_provider_rates_are_normalized(monkeypatch):
    responses = iter(
        [
            {
                "data": {
                    "name": "Publication",
                    "stats": {"average_open_rate": 42.5, "average_click_rate": 3},
                }
            },
            {
                "data": [
                    {
                        "id": "post_1",
                        "title": "Issue",
                        "stats": {
                            "email": {"open_rate": 50, "click_rate": 4},
                            "web": {},
                        },
                    }
                ]
            },
        ]
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(next(responses)).encode()

    monkeypatch.setattr(
        beehiiv_client.urllib.request, "urlopen", lambda request, timeout: Response()
    )
    result = beehiiv_client.publication_performance(
        "pub_sanitized",
        api_key="test-only",
    )

    assert result["avg_open_rate"] == 0.425
    assert result["avg_click_rate"] == 0.03
    assert result["recent_posts"][0]["open_rate"] == 0.5
    assert result["recent_posts"][0]["click_rate"] == 0.04


def test_publication_discovery_returns_only_safe_choices(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(
                {
                    "data": [
                        {"id": "pub_one", "name": "First", "secret": "ignored"},
                        {"id": "pub_two", "name": "Second"},
                    ]
                }
            ).encode()

    monkeypatch.setattr(
        beehiiv_client.urllib.request, "urlopen", lambda request, timeout: Response()
    )
    assert beehiiv_client.list_publications(
        base_url="https://api.sprites.dev/v1/gateway/custom_api/connector",
        auth_mode="sprite_connector",
    ) == [
        {"id": "pub_one", "name": "First"},
        {"id": "pub_two", "name": "Second"},
    ]
