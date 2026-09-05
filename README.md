# Harbor — v0.9.0 production alpha

Harbor is a multi-tenant AI worker platform. The production target is now explicit:

- **Fly Machine** = Harbor control plane.
- **Fly Sprite** = one persistent customer computer per tenant.
- **Fly Connectors** = provider credentials without handing raw keys to worker code.
- **Postgres** = Harbor product state.
- **Workers** = installable capabilities inside the tenant Sprite.

Newsletter Intelligence is worker #1. Alex remains worker #2 and is intentionally blocked until the supplied v3 reconciliation work is complete.

## What changed from v0.8

- added Fly Machine deployment files (`Dockerfile`, `fly.toml`);
- added Postgres/SQLite tenant store and hashed tenant API keys;
- added production HTTP control plane;
- added programmatic Sprite provisioning;
- added runtime wheel upload/install into each tenant Sprite;
- added non-secret Sprite run contract;
- added Fly Connector-compatible beehiiv path;
- removed implicit mock fallback from production;
- added run idempotency state;
- rewrote deployment/product plan around real multi-tenant infrastructure.

Start with `docs/PRODUCTION_PLAN.md`, then `DEPLOY.md`, then `CODEX_NEXT.md`.

## Local tests

The only test path allowed to use sample beehiiv data is explicit mock mode.

```bash
python3 -m pip install -e ".[test]"
python3 -m pytest -q
```

Postgres store tests run when `TEST_DATABASE_URL` points to an isolated test
database. CI supplies an ephemeral PostgreSQL service automatically.

## Production boundary

This package is deployment-ready scaffolding, not a claim that Harbor is already live. A real deployment requires a Fly account/organization, `SPRITE_TOKEN`, Postgres, and a real customer connector. Once those are supplied, the next milestone is one live beehiiv tenant end-to-end on Fly.
