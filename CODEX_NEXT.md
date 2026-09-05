# Codex handoff — Harbor production build

Continue Harbor v0.9.0-production-alpha. Do not redesign the product.

## Fixed architecture

- Harbor control plane runs on Fly Machines.
- One persistent Fly Sprite is provisioned per tenant for v1.
- Workers execute inside the tenant Sprite.
- Provider credentials use Fly Sprites Connectors wherever possible.
- Postgres is the Harbor system of record.
- Newsletter Intelligence is worker #1.
- Alex remains a separate worker and must be reconciled to v3 before it is marked runnable.
- Surfaces are adapters; they never contain business logic.

Read `docs/PRODUCTION_PLAN.md` before changing code.

## Non-negotiables

1. No customer-specific values in source.
2. No plaintext provider credentials in tenant config, DB, logs, reports, run specs, or Sprite files.
3. No implicit mock/sample fallback in production.
4. Remote callers never submit tenant filesystem paths.
5. Every run is tenant-scoped and idempotent.
6. A worker failure is recorded as a failure; do not synthesize a successful report.
7. Provisioning a new tenant must not require editing Python.

## Current code in this alpha

Implemented:

- Fly Machine `Dockerfile` + `fly.toml`.
- production control-plane HTTP API scaffold.
- SQLite local / Postgres production tenant store.
- hashed tenant API keys.
- run idempotency table.
- Sprites lifecycle/filesystem client.
- `SpriteRunner` that provisions a tenant Sprite, uploads the current Harbor wheel, installs it, creates workspace directories, and checkpoints.
- Sprite worker entrypoint using a non-secret run spec.
- Newsletter Intelligence connector path for Fly Connector gateway auth.
- explicit mock mode only.

## Build next in this order

### 1. Harden tenant store

- Move config update methods out of the control-plane module into `TenantStore`.
- Add migration/versioning strategy.
- Add tests against a real temporary Postgres instance in CI.
- Add audit log table.

### 2. Verify Sprites API against a real Fly organization

- Set `SPRITE_TOKEN` in a staging Fly app.
- Provision a Sprite through Harbor.
- Verify runtime-wheel upload.
- Verify `sprites-py` exec behavior.
- Verify checkpoint creation.
- Verify a worker result survives Sprite sleep/wake.
- If the Sprites API/SDK response shape differs, update only the adapter; do not leak Fly specifics into workers.

### 3. Real beehiiv connection

- Create a Fly Custom API Connector for one real beehiiv publication.
- Restrict its policy to the pilot tenant Sprite.
- Store only the returned connector id/gateway base URL and publication id in Harbor.
- Run live `publication_performance` from inside the Sprite.
- Add a sanitized fixture from the real response shape.
- Do not add the raw token to `.env`, tenant JSON, DB, or fixture.

### 4. Scheduler

Implement a scheduler process using tenant timezone + per-worker schedule from Postgres.

- derive one schedule-window idempotency key;
- claim run before dispatch;
- bounded retries for transient Sprites/connector failures;
- never duplicate a completed run;
- persist next/last run status.

Run the scheduler as a second Fly process group or separate Machine process, not from customer Sprites.

### 5. Output adapters

Add an `OutputAdapter` interface and implement email first.

- HTML + text from the existing markdown report;
- tenant-specific destination stored as metadata;
- delivery idempotency;
- delivery audit state;
- provider secret held by the control plane secret store/Fly secret, never per-tenant plaintext.

Then add Slack.

### 6. Remote MCP

Expose authenticated product verbs over remote MCP:

- worker catalog;
- tenant status;
- run worker;
- recent runs;
- enabled workers.

Tenant must be resolved from auth. Remove the old `tenant_config` path parameter from the remote surface.

### 7. Web onboarding

Minimum web UI only:

- create account/workspace;
- show Sprite provisioning state;
- connect source;
- select schedule;
- choose output;
- show last run / connection health.

Do not build an analytics dashboard.

### 8. Second tenant isolation test

Create tenant B and prove:

- different Sprite;
- different connector policy;
- different run records;
- different workspace files;
- tenant A key cannot access tenant B API;
- connector A cannot be called from Sprite B.

### 9. Alex v3 reconciliation

Only after Newsletter Intelligence is live:

- merge Cowork v2.4 improvements into the canonical Alex kernel;
- align the gate skill/runtime with the persistent 8-criterion Gate API;
- replace per-client Data reads with Context API resources;
- install Alex into the tenant Sprite via the same Harbor worker contract;
- verify two workers can coexist in one tenant Sprite without crossing concerns.

## Definition of next release

Do not call the next release beta until one real pilot tenant has:

- a Harbor Fly deployment;
- Postgres tenant state;
- a provisioned Sprite;
- a real beehiiv connector;
- a scheduled live pull;
- one delivered morning report;
- one persisted run record;
- zero mock data;
- no source-code edit for customer-specific configuration.
