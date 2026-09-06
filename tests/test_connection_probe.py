from harbor import connection_probe


def _spec():
    return {
        "tenant_id": "acme",
        "name": "Acme",
        "workspace": "/workspace",
        "workers": ["newsletter-intelligence"],
        "connections": [
            {
                "id": "bee-main",
                "provider": "beehiiv",
                "settings": {
                    "auth_mode": "sprite_connector",
                    "gateway_base_url": "https://api.sprites.dev/v1/gateway/custom_api/bee-main",
                    "publication_id": "pub_example",
                },
            }
        ],
        "provider": "beehiiv",
    }


def test_probe_returns_safe_verified_metadata(monkeypatch):
    def verify(publication_id, **kwargs):
        assert publication_id == "pub_example"
        assert kwargs["auth_mode"] == "sprite_connector"
        return {
            "publication_id": publication_id,
            "publication_name": "Example newsletter",
            "organization_name": "Acme",
        }

    monkeypatch.setattr(connection_probe.beehiiv_client, "verify_publication", verify)
    result = connection_probe.probe(_spec())
    assert result["status"] == "verified"
    assert result["publication_name"] == "Example newsletter"
    assert "token" not in str(result).lower()


def test_probe_surfaces_provider_failure(monkeypatch):
    def fail(*args, **kwargs):
        raise connection_probe.beehiiv_client.BeehiivError(
            "beehiiv_http_error", "401 unauthorized"
        )

    monkeypatch.setattr(connection_probe.beehiiv_client, "verify_publication", fail)
    result = connection_probe.probe(_spec())
    assert result == {
        "status": "failed",
        "provider": "beehiiv",
        "checked_at": result["checked_at"],
        "error": {"kind": "beehiiv_http_error", "detail": "401 unauthorized"},
    }
