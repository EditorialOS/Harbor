"""Fixed-purpose connection probe executed inside a tenant Sprite."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from . import beehiiv_client
from .config import ConfigError
from .sprite_entrypoint import tenant_from_spec


def probe(spec: dict) -> dict:
    checked_at = dt.datetime.now(dt.timezone.utc).isoformat()
    provider = spec["provider"]
    try:
        tenant = tenant_from_spec(spec)
        connection = tenant.connection(provider)
        if provider != "beehiiv":
            raise ConfigError(f"unsupported connection provider '{provider}'")
        publication_id = connection.settings.get("publication_id")
        if not publication_id:
            publications = beehiiv_client.list_publications(
                base_url=connection.settings.get("gateway_base_url"),
                auth_mode=connection.settings.get("auth_mode", "bearer"),
            )
            return {
                "status": "selection_required" if len(publications) > 1 else "discovered",
                "provider": provider,
                "checked_at": checked_at,
                "publications": publications,
            }
        metadata = beehiiv_client.verify_publication(
            publication_id,
            base_url=connection.settings.get("gateway_base_url"),
            auth_mode=connection.settings.get("auth_mode", "bearer"),
        )
        return {
            "status": "verified",
            "provider": provider,
            "checked_at": checked_at,
            **metadata,
        }
    except beehiiv_client.BeehiivError as error:
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
