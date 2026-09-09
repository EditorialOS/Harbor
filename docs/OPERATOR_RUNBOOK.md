# Operator runbook

## Normal checks

- `GET /readyz` must return HTTP 200 and the current database schema version.
- `GET /status` must show **Operational**.
- `/metrics` must report `harbor_metrics_up 1`, a healthy recent scheduler
  heartbeat, zero overdue schedules, and zero expired run leases.
- The Fly app must have one healthy `app` Machine and one healthy `scheduler`
  Machine.

Use Fly logs only for investigation. Never print environment values, request
authorization headers, connector credentials, report bodies, or customer data.

## Deploying a release

1. Back up production Postgres before a release containing a migration.
2. Run the complete local test suite and build the wheel and Docker image.
3. Confirm `git status --short` is empty and deploy the committed revision.
4. Wait for both Fly process groups to pass checks.
5. Verify `/readyz`, `/status`, `/metrics`, unauthenticated MCP rejection, an
   authenticated MCP read, scheduler heartbeat, and one tenant-scoped run.
6. Record only sanitized acceptance evidence.

Harbor migrations are transactional and protected by a Postgres advisory lock.
A migration failure must stop the release; do not bypass schema readiness.

## Failed scheduled run

1. Check the tenant's recent runs and activity log for status and attempt count.
2. Check aggregate metrics and sanitized Fly logs for the failure category.
3. Confirm the tenant Sprite is ready and its connector is verified.
4. Fix the external condition, then use the normal retry control. Do not modify
   a run record, reuse another tenant's connection, or mark a failure complete.

The scheduler retries a run at most three times with exponential delay. The
same schedule window, run id, and delivery idempotency key are retained.

## Scheduler or database incident

- If readiness fails, inspect database reachability and migration state first.
- If the scheduler heartbeat is stale, inspect the scheduler Machine and restart
  that process group only after checking for an active run lease.
- Harbor executes at most one overdue window after an outage; it does not create
  a backlog storm.
- Restore Postgres from the provider backup procedure only after preserving the
  current database and documenting the recovery point.

## Connector incident

- A customer reconnects from Harbor's password field; the key goes directly to
  Fly's connector API and is not retained by Harbor.
- Verify the connector policy names only the intended tenant Sprite and permits
  only required beehiiv paths.
- Do not broaden one connector to multiple tenant Sprites as a workaround.

## Billing incident

- Stripe webhook endpoint: `/stripe/webhook`.
- Webhooks must pass raw-body signature verification before state changes.
- Stripe event ids are persisted for exactly-once processing; full webhook
  payloads are not stored.
- `active` and `trialing` permit paid-tenant runs. Cancellation and unpaid states
  block new runs while preserving the tenant's records and files.
- Re-send an event from Stripe rather than manually changing subscription rows.

## Secret rotation

Rotate platform secrets in their provider and Fly secret store, deploy/restart
the affected process, and verify health. Provider credentials belong in Fly
Connectors, not Harbor secrets or Postgres. Never copy a secret into an issue,
commit, report, run spec, or support transcript.

## Escalation

Before commercial launch, configure a real external alert destination and name
the on-call owner. Treat database unavailability, stale scheduler heartbeat,
expired leases, repeated delivery failures, OAuth failure spikes, or tenant
isolation failures as operator-actionable incidents.
