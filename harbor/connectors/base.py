"""Infrastructure-independent data connector contract and registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..config import ConnectionConfig
from ..newsletter_model import DateWindow, NewsletterDataset


class ConnectorError(RuntimeError):
    def __init__(self, provider: str, kind: str, detail: str):
        self.provider = provider
        self.kind = kind
        self.detail = detail
        super().__init__(f"{provider} {kind}: {detail}")


@dataclass(frozen=True)
class NewsletterRequest:
    window: DateWindow
    publication_ids: tuple[str, ...] = ()
    issue_limit: int = 100
    allow_mock: bool = False

    def __post_init__(self) -> None:
        if self.issue_limit < 1 or self.issue_limit > 1000:
            raise ValueError("issue_limit must be between 1 and 1000")


class DataConnector(Protocol):
    provider: str
    source_type: str
    capabilities: frozenset[str]

    def discover(self, connection: ConnectionConfig) -> list[dict[str, str | None]]: ...

    def verify(
        self, connection: ConnectionConfig, resource_id: str
    ) -> dict[str, str | None]: ...

    def sync(
        self, connection: ConnectionConfig, request: NewsletterRequest
    ) -> NewsletterDataset: ...


_CONNECTORS: dict[tuple[str, str], DataConnector] = {}


def register_connector(connector: DataConnector) -> DataConnector:
    key = (connector.source_type, connector.provider)
    if key in _CONNECTORS:
        raise ValueError(f"connector already registered for {key}")
    _CONNECTORS[key] = connector
    return connector


def connector_for(source_type: str, provider: str) -> DataConnector:
    try:
        return _CONNECTORS[(source_type, provider)]
    except KeyError as error:
        raise ConnectorError(
            provider, "unsupported_provider", f"no {source_type} connector is installed"
        ) from error


def providers_for(source_type: str) -> tuple[str, ...]:
    return tuple(
        sorted(provider for kind, provider in _CONNECTORS if kind == source_type)
    )
