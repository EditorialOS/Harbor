import pytest

from harbor.broker_auth import (
    BrokerAuthError,
    issue_broker_grant,
    verify_broker_grant,
)

KEY = "test-broker-signing-key-with-more-than-32-bytes"


def test_broker_grant_is_scoped_and_expires():
    token = issue_broker_grant(
        tenant_id="tenant-a",
        connection_id="ca_kit_a",
        provider="kit",
        run_id="run_one",
        now=1_000,
        signing_key=KEY,
    )

    grant = verify_broker_grant(
        token,
        expected_connection_id="ca_kit_a",
        expected_provider="kit",
        now=1_001,
        signing_key=KEY,
    )
    assert grant.tenant_id == "tenant-a"
    assert grant.run_id == "run_one"

    with pytest.raises(BrokerAuthError, match="scope"):
        verify_broker_grant(
            token,
            expected_connection_id="ca_kit_b",
            expected_provider="kit",
            now=1_001,
            signing_key=KEY,
        )
    with pytest.raises(BrokerAuthError, match="expired"):
        verify_broker_grant(
            token,
            expected_connection_id="ca_kit_a",
            expected_provider="kit",
            now=4_600,
            signing_key=KEY,
        )


def test_broker_grant_rejects_tampering_and_short_keys():
    token = issue_broker_grant(
        tenant_id="tenant-a",
        connection_id="ca_kit_a",
        provider="kit",
        run_id="run_one",
        signing_key=KEY,
    )
    encoded, signature = token.split(".")
    with pytest.raises(BrokerAuthError, match="invalid"):
        verify_broker_grant(
            f"{encoded}x.{signature}",
            expected_connection_id="ca_kit_a",
            expected_provider="kit",
            signing_key=KEY,
        )
    with pytest.raises(BrokerAuthError, match="32 bytes"):
        issue_broker_grant(
            tenant_id="tenant-a",
            connection_id="ca_kit_a",
            provider="kit",
            run_id="run_one",
            signing_key="too-short",
        )
