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

## Scheduler and unattended live execution completed

- A dedicated Fly process group discovers tenant schedules from Postgres.
- Schedule state persists next run, last run, status, attempts, and errors.
- Schedule-window idempotency prevents duplicate dispatch.
- Retries are bounded and reuse one run id and report artifact.
- Tenant time-zone changes are validated and updated through the authenticated
  control-plane API; customer-specific values remain database state.
- Long outages execute at most one overdue window rather than creating a
  backlog storm.
- The dedicated scheduler Machine is deployed and a real scheduled beehiiv
  pull completed without operator intervention.
- Expiring run leases let a restarted scheduler reclaim an interrupted run
  without changing its run id or delivery idempotency key.

## Output and product surfaces implemented

- Email delivery renders the Sprite report as escaped HTML and plain text.
- Delivery claims, attempts, provider receipt ids, failures, and deduplication
  are durable Postgres state; recipients remain tenant runtime metadata.
- The email provider credential is accepted only from the control-plane secret
  environment and is never included in run specs, tenant state, or reports.
- A stateless Streamable HTTP MCP endpoint is mounted at `/mcp`, authenticates
  tenant bearer keys before parsing MCP requests, and resolves tenant identity
  from the credential rather than a tool argument.
- MCP exposes worker catalog, safe tenant status, enabled workers, recent runs,
  and idempotent worker execution. Its schemas expose no tenant-config or
  filesystem-path parameter.

## Live email and tenant-isolation evidence completed

- A real Resend account is configured through Fly secrets, and a completed live
  beehiiv report was delivered and visibly rendered in the pilot inbox.
- The delivery receipt, attempt count, and completed run are durable Postgres
  state; the provider secret is absent from tenant state, run state, and the
  Sprite report.
- A second tenant was created through the same API and Harbor automatically
  provisioned a distinct persistent Sprite with the current runtime.
- Cross-tenant HTTP authentication returned 401 in both directions, and the
  remote MCP surface resolved the second tenant only from its own bearer key.
- The two tenants exposed disjoint run histories and workspace files.
- The pilot Sprite received HTTP 200 through its beehiiv connector while the
  second tenant Sprite received HTTP 403 for that same connector gateway,
  proving the live Fly Connector policy boundary.

## Still required before commercial launch

- Verify a custom email-sending domain before delivering to addresses other
  than the Resend account owner. The current testing sender is intentionally
  limited to the verified account address.
- Monitoring/alerts around the implemented retry policy.
- Minimum end-user web onboarding and connector setup UX.
- OAuth-based end-user onboarding for ChatGPT; direct bearer-authenticated MCP
  is available to clients that support custom authorization headers.

## Deliberately not faked

- No customer API key is embedded as an example production secret.
- No fake production metrics are returned when a live connector is absent.
- Alex v3 is still not marked runnable until the documented reconciliation is completed.
