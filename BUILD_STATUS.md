# Build status — v0.9.0-production-alpha

## Implemented in this slice

- Production architecture changed to Fly Machine control plane + per-tenant Fly Sprite execution.
- Fly deployment configuration and production Docker image.
- Postgres production tenant store with SQLite local mode.
- Hashed tenant API keys.
- Run idempotency records.
- Official `sprites-py` lifecycle, paginated listing, filesystem, exec, and
  checkpoint paths behind Harbor's infrastructure adapter.
- Programmatic tenant Sprite provisioning.
- Runtime wheel is uploaded from the control-plane release into the Sprite; no per-customer source edits.
- Persistent `/workspace` creation and a required successful post-install
  checkpoint.
- Non-secret run spec and in-Sprite worker entrypoint.
- Newsletter Intelligence can call beehiiv through a Fly Connector gateway.
- Implicit fake-data fallback removed; mock mode is explicit test-only behavior.
- Product/deployment/Codex plans rewritten around real infrastructure.

## Tenant-store hardening completed after the alpha handoff

- Ordered transactional schema migrations with a Postgres startup lock.
- Tenant/worker-scoped run idempotency instead of one global key namespace.
- Store-owned tenant configuration and connector metadata updates.
- Tenant-scoped audit log for tenant, connection, Sprite, and run state changes.
- Secret-shaped metadata is rejected before it reaches database state or run specs.
- Inactive tenant keys no longer authenticate.
- Production/Fly startup fails if `DATABASE_URL` is absent.
- SQLite migration tests and a real ephemeral-Postgres CI job.
- Runtime wheel packaging and the Fly control-plane Docker image now build.
- Sprite wheel upload preserves the valid wheel filename; checkpoint failure is visible.
- Sprite run specs now use a Harbor-generated run id, a unique internal path,
  and mode-0600 permissions; the same run id reaches worker artifacts.

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
