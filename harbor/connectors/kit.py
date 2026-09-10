"""Kit API v4 adapter for Harbor's normalized newsletter contract."""

from __future__ import annotations

import datetime as dt
import statistics
from typing import Any

from .. import kit_client
from ..config import ConnectionConfig
from ..newsletter_model import (
    MetricState,
    MetricValue,
    NewsletterDataset,
    NewsletterIssue,
    NewsletterPublication,
    provider_metric,
)
from ..secrets import resolve
from .base import ConnectorError, NewsletterRequest, register_connector


def _count(value: Any, *, supported: bool = True) -> MetricValue:
    return provider_metric(value, provider="Kit", supported=supported)


def _rate(value: Any, *, supported: bool = True) -> MetricValue:
    if not supported:
        return MetricValue.not_supported("Kit")
    return provider_metric(kit_client.normalize_rate(value), provider="Kit", rate=True)


def _mean(issues: tuple[NewsletterIssue, ...], name: str) -> MetricValue:
    values = [
        float(metric.value)
        for issue in issues
        if (metric := getattr(issue, name)).state is MetricState.AVAILABLE
    ]
    return (
        MetricValue.available(statistics.fmean(values))
        if values
        else MetricValue.no_data("Kit returned no comparable completed broadcasts")
    )


class KitNewsletterConnector:
    provider = "kit"
    source_type = "newsletter"
    capabilities = frozenset(
        {
            "account_discovery",
            "subscriber_counts",
            "subscriber_growth",
            "issues",
            "recipients",
            "opens",
            "open_rate",
            "clicks",
            "click_rate",
            "unsubscribes",
            "unsubscribe_rate",
            "subject_lines",
            "audience_tags",
            "date_filtering",
        }
    )

    def _auth(self, connection: ConnectionConfig) -> tuple[str, str | None, str | None]:
        auth_mode = connection.settings.get("auth_mode", "sprite_connector")
        if auth_mode == "harbor_broker":
            credential = connection.settings.get("broker_authorization")
            base_url = connection.settings.get("broker_base_url")
        else:
            credential = (
                resolve(connection.secret_ref, required=False)
                if auth_mode in {"oauth_bearer", "api_key"}
                else None
            )
            base_url = connection.settings.get(
                "gateway_base_url"
            ) or connection.settings.get("base_url")
        return auth_mode, credential, base_url

    def discover(self, connection: ConnectionConfig) -> list[dict[str, str | None]]:
        account = self._account(connection)
        return [{"id": account["account_id"], "name": account["account_name"]}]

    def verify(
        self, connection: ConnectionConfig, resource_id: str
    ) -> dict[str, str | None]:
        account = self._account(connection)
        if str(account["account_id"]) != str(resource_id):
            raise ConnectorError(
                self.provider,
                "account_not_found",
                "the selected Kit account is not available to this connection",
            )
        return {
            "publication_id": account["account_id"],
            "publication_name": account["account_name"],
            "organization_name": account["account_name"],
        }

    def _account(self, connection: ConnectionConfig) -> dict[str, str | None]:
        auth_mode, credential, base_url = self._auth(connection)
        try:
            return kit_client.current_account(
                credential=credential, base_url=base_url, auth_mode=auth_mode
            )
        except kit_client.KitError as error:
            raise ConnectorError(self.provider, error.kind, error.detail) from error

    def sync(
        self, connection: ConnectionConfig, request: NewsletterRequest
    ) -> NewsletterDataset:
        if request.allow_mock:
            raise ConnectorError(
                self.provider,
                "mock_not_available",
                "Kit has no automatic mock data path",
            )
        auth_mode, credential, base_url = self._auth(connection)
        try:
            account = kit_client.current_account(
                credential=credential, base_url=base_url, auth_mode=auth_mode
            )
            selected_ids = request.publication_ids or tuple(
                str(value)
                for value in (
                    connection.settings.get("publication_ids")
                    or [connection.settings.get("publication_id")]
                )
                if value is not None
            )
            if selected_ids and str(account["account_id"]) not in selected_ids:
                raise ConnectorError(
                    self.provider,
                    "account_not_found",
                    "the selected Kit account is not available to this connection",
                )
            subscriber_count = kit_client.active_subscriber_count(
                credential=credential, base_url=base_url, auth_mode=auth_mode
            )
            sent_after = (
                request.window.start.isoformat() if request.window.start else None
            )
            sent_before = request.window.end.isoformat() if request.window.end else None
            broadcast_result = kit_client.broadcast_stats(
                limit=request.issue_limit,
                sent_after=sent_after,
                sent_before=sent_before,
                credential=credential,
                base_url=base_url,
                auth_mode=auth_mode,
            )
            tags = kit_client.list_tags(
                credential=credential, base_url=base_url, auth_mode=auth_mode
            )
            growth = None
            if request.window.start is not None and request.window.end is not None:
                growth = kit_client.growth_stats(
                    starting=request.window.start.date().isoformat(),
                    ending=request.window.end.date().isoformat(),
                    credential=credential,
                    base_url=base_url,
                    auth_mode=auth_mode,
                )
        except kit_client.KitError as error:
            raise ConnectorError(self.provider, error.kind, error.detail) from error

        issues = tuple(
            self._issue(item) for item in broadcast_result.get("broadcasts", [])
        )
        publication = NewsletterPublication(
            provider=self.provider,
            connection_id=connection.id,
            provider_id=str(account["account_id"]),
            name=account["account_name"],
            subscribers=_count(subscriber_count),
            free_subscribers=_count(None, supported=False),
            paid_subscribers=_count(None, supported=False),
            total_subscribers=_count(subscriber_count),
            subscriber_growth=(
                _count(growth.get("net_new_subscribers"))
                if growth is not None
                else MetricValue.insufficient_history(
                    "Select a date range to calculate Kit subscriber growth"
                )
            ),
            sends=_count(
                broadcast_result.get("total_count")
                if broadcast_result.get("total_count") is not None
                else len(issues)
            ),
            average_open_rate=_mean(issues, "open_rate"),
            average_click_rate=_mean(issues, "click_rate"),
            issues=issues,
            segments=tuple(tags),
            metadata={"account_timezone": account.get("timezone")},
        )
        return NewsletterDataset(
            window=request.window,
            publications=(publication,),
            capabilities=tuple(sorted(self.capabilities)),
            captured_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        )

    @staticmethod
    def _issue(row: dict[str, Any]) -> NewsletterIssue:
        stats = row.get("stats") or {}
        if not isinstance(stats, dict):
            stats = {}
        open_supported = not bool(stats.get("open_tracking_disabled"))
        click_supported = not bool(stats.get("click_tracking_disabled"))
        return NewsletterIssue(
            provider_id=str(row["id"]) if row.get("id") is not None else None,
            title=row.get("subject"),
            subject_line=row.get("subject"),
            sent_at=row.get("send_at"),
            recipients=_count(stats.get("recipients")),
            delivered=_count(None, supported=False),
            opens=_count(stats.get("emails_opened"), supported=open_supported),
            unique_opens=_count(None, supported=False),
            open_rate=_rate(stats.get("open_rate"), supported=open_supported),
            clicks=_count(stats.get("total_clicks"), supported=click_supported),
            unique_clicks=_count(None, supported=False),
            click_rate=_rate(stats.get("click_rate"), supported=click_supported),
            unsubscribes=_count(stats.get("unsubscribes")),
            unsubscribe_rate=_rate(stats.get("unsubscribe_rate")),
            spam_reports=_count(None, supported=False),
            web_views=_count(None, supported=False),
            web_clicks=_count(None, supported=False),
            metadata={"status": stats.get("status")},
        )


CONNECTOR = register_connector(KitNewsletterConnector())
