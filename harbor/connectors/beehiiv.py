"""Beehiiv adapter for Harbor's normalized newsletter contract."""

from __future__ import annotations

import datetime as dt
from typing import Any

from .. import beehiiv_client
from ..config import ConnectionConfig
from ..newsletter_model import (
    MetricValue,
    NewsletterDataset,
    NewsletterIssue,
    NewsletterPublication,
    provider_metric,
)
from ..secrets import resolve
from .base import ConnectorError, NewsletterRequest, register_connector


def _rate(value: Any) -> MetricValue:
    return provider_metric(value, provider="Beehiiv", rate=True)


def _count(value: Any) -> MetricValue:
    return provider_metric(value, provider="Beehiiv")


def _unsubscribe_rate(row: dict[str, Any]) -> MetricValue:
    recipients = row.get("recipients")
    unsubscribes = row.get("unsubscribes")
    if recipients is None or unsubscribes is None:
        return MetricValue.no_data("Beehiiv did not return enough data to calculate it")
    if int(recipients) == 0:
        return MetricValue.no_data("Cannot calculate a rate with zero recipients")
    return MetricValue.available(int(unsubscribes) / int(recipients))


class BeehiivNewsletterConnector:
    provider = "beehiiv"
    source_type = "newsletter"
    capabilities = frozenset(
        {
            "publication_discovery",
            "subscriber_counts",
            "issues",
            "recipients",
            "delivery",
            "opens",
            "unique_opens",
            "open_rate",
            "clicks",
            "unique_clicks",
            "click_rate",
            "unsubscribes",
            "spam_reports",
            "web_engagement",
            "subject_lines",
        }
    )

    def _auth(self, connection: ConnectionConfig) -> tuple[str, str | None, str | None]:
        auth_mode = connection.settings.get("auth_mode", "bearer")
        api_key = (
            resolve(connection.secret_ref, required=False)
            if auth_mode == "bearer"
            else None
        )
        base_url = connection.settings.get(
            "gateway_base_url"
        ) or connection.settings.get("base_url")
        return auth_mode, api_key, base_url

    def discover(self, connection: ConnectionConfig) -> list[dict[str, str | None]]:
        auth_mode, api_key, base_url = self._auth(connection)
        try:
            return beehiiv_client.list_publications(
                api_key=api_key,
                base_url=base_url,
                auth_mode=auth_mode,
            )
        except beehiiv_client.BeehiivError as error:
            raise ConnectorError(self.provider, error.kind, error.detail) from error

    def verify(
        self, connection: ConnectionConfig, resource_id: str
    ) -> dict[str, str | None]:
        auth_mode, api_key, base_url = self._auth(connection)
        try:
            return beehiiv_client.verify_publication(
                resource_id,
                api_key=api_key,
                base_url=base_url,
                auth_mode=auth_mode,
            )
        except beehiiv_client.BeehiivError as error:
            raise ConnectorError(self.provider, error.kind, error.detail) from error

    def sync(
        self, connection: ConnectionConfig, request: NewsletterRequest
    ) -> NewsletterDataset:
        publication_ids = request.publication_ids
        if not publication_ids:
            configured = connection.settings.get("publication_ids") or []
            legacy = connection.settings.get("publication_id")
            publication_ids = tuple(str(item) for item in configured)
            if not publication_ids and legacy:
                publication_ids = (str(legacy),)
        if not publication_ids:
            raise ConnectorError(
                self.provider,
                "publication_selection_required",
                "select at least one publication",
            )

        auth_mode, api_key, base_url = self._auth(connection)
        publications: list[NewsletterPublication] = []
        is_mock = False
        for publication_id in publication_ids:
            try:
                raw = beehiiv_client.publication_performance(
                    publication_id,
                    request.issue_limit,
                    api_key=api_key,
                    base_url=base_url,
                    auth_mode=auth_mode,
                    allow_mock=request.allow_mock,
                )
            except beehiiv_client.BeehiivError as error:
                raise ConnectorError(self.provider, error.kind, error.detail) from error
            is_mock = is_mock or bool(raw.get("_mock"))
            issues = tuple(self._issue(item) for item in raw.get("recent_posts", []))
            publications.append(
                NewsletterPublication(
                    provider=self.provider,
                    connection_id=connection.id,
                    provider_id=publication_id,
                    name=raw.get("publication_name"),
                    subscribers=_count(raw.get("active_subscribers")),
                    free_subscribers=_count(raw.get("active_free_subscribers")),
                    paid_subscribers=_count(raw.get("active_premium_subscribers")),
                    total_subscribers=_count(raw.get("total_subscribers")),
                    subscriber_growth=MetricValue.insufficient_history(),
                    sends=_count(raw.get("total_sent")),
                    average_open_rate=_rate(raw.get("avg_open_rate")),
                    average_click_rate=_rate(raw.get("avg_click_rate")),
                    issues=issues,
                    metadata={"organization_name": raw.get("organization_name")},
                )
            )

        return NewsletterDataset(
            window=request.window,
            publications=tuple(publications),
            capabilities=tuple(sorted(self.capabilities)),
            captured_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            mock=is_mock,
        )

    @staticmethod
    def _issue(row: dict[str, Any]) -> NewsletterIssue:
        tags = row.get("content_tags") or row.get("tags") or []
        return NewsletterIssue(
            provider_id=row.get("id"),
            title=row.get("title"),
            subject_line=row.get("subject_line") or row.get("title"),
            sent_at=row.get("published"),
            audience=row.get("audience"),
            tags=tuple(str(item) for item in tags if item),
            recipients=_count(row.get("recipients")),
            delivered=_count(row.get("delivered")),
            opens=_count(row.get("opens")),
            unique_opens=_count(row.get("unique_opens")),
            open_rate=_rate(row.get("open_rate")),
            clicks=_count(row.get("clicks")),
            unique_clicks=_count(row.get("unique_clicks")),
            click_rate=_rate(row.get("click_rate")),
            unsubscribes=_count(row.get("unsubscribes")),
            unsubscribe_rate=_unsubscribe_rate(row),
            spam_reports=_count(row.get("spam_reports")),
            web_views=_count(row.get("web_views")),
            web_clicks=_count(row.get("web_clicks")),
            metadata={"upgrades": row.get("upgrades")},
        )


CONNECTOR = register_connector(BeehiivNewsletterConnector())
