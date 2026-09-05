# Build status — v0.9.0-production-alpha

## Implemented in this slice

- Production architecture changed to Fly Machine control plane + per-tenant Fly Sprite execution.
- Fly deployment configuration and production Docker image.
- Postgres production tenant store with SQLite local mode.
- Hashed tenant API keys.
- Run idempotency records.
- Sprites API adapter for lifecycle/filesystem calls.
- Official `sprites-py` exec path.
- Programmatic tenant Sprite provisioning.
- Runtime wheel is uploaded from the control-plane release into the Sprite; no per-customer source edits.
- Persistent `/workspace` creation and post-install checkpoint attempt.
- Non-secret run spec and in-Sprite worker entrypoint.
- Newsletter Intelligence can call beehiiv through a Fly Connector gateway.
- Implicit fake-data fallback removed; mock mode is explicit test-only behavior.
- Product/deployment/Codex plans rewritten around real infrastructure.

## Still required for first live pilot

- Actual Fly credentials/account connection.
- Actual Postgres instance.
- Actual pilot beehiiv connector and publication id.
- Live validation of the current Sprites API/SDK adapter against the pilot organization.
- Scheduler process.
- Email delivery adapter.
- monitoring and retry policy.
- second-tenant isolation test.

## Deliberately not faked

- No claim that the code is deployed; no Fly credentials were available in this build environment.
- No customer API key is embedded as an example production secret.
- No fake production metrics are returned when a live connector is absent.
- Alex v3 is still not marked runnable until the documented reconciliation is completed.
