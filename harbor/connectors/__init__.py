"""Harbor data connector registry."""

from .base import (
    ConnectorError,
    DataConnector,
    NewsletterRequest,
    connector_for,
    register_connector,
)

__all__ = [
    "ConnectorError",
    "DataConnector",
    "NewsletterRequest",
    "connector_for",
    "register_connector",
]
