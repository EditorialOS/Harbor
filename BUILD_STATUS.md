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

## Live pilot evidence completed

- The Fly control plane is deployed against production Postgres state.
- Harbor provisioned and verified a persistent tenant Sprite through the live
  Sprites API, including wheel installation, command behavior, checkpointing,
  cold wake, and persistent workspace files.
- A policy-restricted Fly Custom API Connector was verified from inside that
  tenant Sprite against a real beehiiv publication.
- Newsletter Intelligence completed a real, zero-mock run; the Postgres run,
  Sprite run artifact, and report artifact were reconciled by run id and hash.
- A sanitized regression fixture preserves the verified beehiiv response shape
  without retaining customer content or credentials.

## Scheduler implemented, pending paid Machine deployment

- A dedicated Fly process group discovers tenant schedules from Postgres.
- Schedule state persists next run, last run, status, attempts, and errors.
- Schedule-window idempotency prevents duplicate dispatch.
- Retries are bounded and reuse one run id and report artifact.
- Tenant time-zone changes are validated and updated through the authenticated
  control-plane API; customer-specific values remain database state.
- Long outages execute at most one overdue window rather than creating a
  backlog storm.

## Still required for first live pilot

- Deploy the scheduler process group on one additional paid Fly Machine and
  verify one scheduled live pull.
- Email delivery adapter.
- Monitoring/alerts around the implemented retry policy.
- Authenticated remote MCP surface.
- second-tenant isolation test.

## Deliberately not faked

- No customer API key is embedded as an example production secret.
- No fake production metrics are returned when a live connector is absent.
- Alex v3 is still not marked runnable until the documented reconciliation is completed.
