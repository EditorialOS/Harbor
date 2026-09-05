import pytest

from harbor import core, deck_client


def test_deck_requires_live_credentials_or_explicit_mock(monkeypatch):
    monkeypatch.delenv("DECK_API_KEY", raising=False)

    with pytest.raises(deck_client.DeckError, match="mock mode is explicit only"):
        deck_client.run_task("task_dev", "connection", {})

    result = deck_client.run_task("task_dev", "connection", {}, allow_mock=True)
    assert result["_mock"] is True


def test_source_catalog_contains_no_customer_deck_task_ids():
    assert all("deck_task" not in job for job in core.CATALOG.values())
