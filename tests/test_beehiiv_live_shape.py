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
        "title": "Sanitized issue",
        "published": "2026-09-05T12:00:00Z",
        "recipients": 0,
        "open_rate": 0.0,
        "click_rate": 0.0,
        "opens": 0,
        "clicks": 0,
        "web_views": 0,
    }
    assert len(requests) == 2
    assert all(request.get_header("Authorization") is None for request in requests)
