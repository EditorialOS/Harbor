"""Fixed-purpose connection probe executed inside a tenant Sprite."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from .config import ConfigError
from .connectors import ConnectorError, connector_for
from .connectors import beehiiv as _beehiiv_connector  # noqa: F401
from .sprite_entrypoint import tenant_from_spec


def probe(spec: dict) -> dict:
    checked_at = dt.datetime.now(dt.timezone.utc).isoformat()
    provider = spec["provider"]
    try:
        tenant = tenant_from_spec(spec)
        connection = tenant.connection(provider)
        connector = connector_for("newsletter", provider)
        publication_id = connection.settings.get("publication_id")
        if not publication_id:
            publications = connector.discover(connection)
            return {
                "status": "selection_required" if len(publications) > 1 else "discovered",
                "provider": provider,
                "checked_at": checked_at,
                "publications": publications,
            }
        metadata = connector.verify(connection, publication_id)
        return {
            "status": "verified",
            "provider": provider,
            "checked_at": checked_at,
            **metadata,
        }
    except ConnectorError as error:
        return {
            "status": "failed",
            "provider": provider,
            "checked_at": checked_at,
            "error": {"kind": error.kind, "detail": error.detail},
        }
    except (ConfigError, KeyError, ValueError) as error:
        return {
            "status": "failed",
            "provider": provider,
            "checked_at": checked_at,
            "error": {"kind": "invalid_connection", "detail": str(error)},
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    args = parser.parse_args()
    result = probe(json.loads(Path(args.spec).read_text()))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
