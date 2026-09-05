# Harbor Production Plan — Fly Machines + Fly Sprites

Version: 0.9.0-alpha
Goal: turn Harbor from a local worker runtime into a real multi-tenant product with real customer data, real credentials, real isolated computers, and a real public control plane.

## Product definition

Harbor is a commercial AI worker platform. A customer gets one Harbor workspace and can install workers into it. The first sellable worker is Newsletter Intelligence. Alex is the next larger worker after its v3 reconciliation.

The customer does not operate Python, cron, VPS scripts, or tenant JSON files. The customer connects services, chooses workers, chooses delivery surfaces, and Harbor runs them.

## Production architecture

```text
Customer surfaces
ChatGPT / Codex / email / Slack / web
            |
            v
+----------------------------------+
| Harbor Control Plane             |
| Fly Machine                      |
|                                  |
| auth + tenancy                   |
| worker catalog                   |
| schedules + idempotency          |
| connector metadata               |
| tenant -> Sprite routing         |
| MCP / HTTP API                   |
+----------------+-----------------+
                 |
                 | Sprites API
                 v
        +---------------------+
        | Tenant Sprite       |
        | persistent computer |
        |                     |
        | /workspace          |
        | installed workers   |
        | skills              |
        | reports / run files |
        +----------+----------+
                   |
                   | Fly Connector gateway
                   v
        real customer services
        beehiiv / GitHub / Slack / APIs

Shared services used by workers when needed:
- Context API
- Gate API
- model providers
- delivery providers
```

## What runs where

### Fly Machine: Harbor control plane

Long-running trusted service. It owns:

- customer/tenant identity;
- tenant API keys and future session auth;
- subscription/entitlement state;
- worker catalog and enabled-worker state;
- schedules;
- run state and idempotency;
- mapping from tenant to Sprite;
- non-secret connector metadata;
- public HTTP API;
- remote MCP surface;
- provisioning and dispatch.

The Machine does **not** contain each customer's working files and does not run arbitrary worker code directly.

### Fly Sprite: customer computer

One persistent Sprite per tenant for v1. It owns:

- the customer's Harbor workspace;
- installed worker runtime;
- installed skills;
- generated reports and intermediate files;
- persistent local working state;
- execution of worker code.

The Sprite is private by default. It is not the public Harbor API.

### Fly Connectors: customer credentials

Provider credentials should live in Fly's connector layer wherever the provider can be reached through it. The tenant Sprite calls the connector gateway and never receives the raw credential.

For beehiiv, the first production pilot uses a custom API connector pointing at `https://api.beehiiv.com/v2`. Harbor stores only the connector id/gateway base URL and publication id.

No beehiiv token is written to:

- tenant config;
- Postgres;
- Sprite environment;
- worker run spec;
- reports;
- logs.

### Postgres: Harbor system of record

Production `DATABASE_URL` points to Postgres. It stores product metadata, not provider secrets:

- tenants;
- worker entitlements;
- schedules;
- Sprite identifiers;
- connector identifiers and safe configuration;
- run records;
- delivery state;
- audit metadata.

## No-hardcoding rule

No customer-specific operational value may live in source code.

The following are runtime data and must come from onboarding/configuration/database state:

- tenant id and name;
- timezone;
- publication ids;
- connection ids;
- connector gateway URLs;
- Sprite names;
- enabled workers;
- worker schedule;
- output destinations;
- Context API workspace/key reference;
- Gate API key reference;
- Slack channels;
- email recipients;
- model choice where configurable.

Platform-level deployment values are environment/secrets, not source constants:

- `DATABASE_URL`;
- `SPRITE_TOKEN`;
- `HARBOR_ADMIN_TOKEN`;
- delivery-provider credentials;
- OpenAI/other model credentials if the worker uses a direct provider rather than a connector;
- public app URL.

The only source constants should be product protocol defaults such as HTTP port 8080 and versioned API paths.

## Real-data rule

Production never silently substitutes sample data.

Newsletter Intelligence has two modes:

- `live`: default in production; a connection failure fails the run and is recorded;
- `mock`: explicit developer/test-only mode.

A completed production run must identify the real connector used and must not contain `_mock=true` anywhere in its execution record.

## Tenant provisioning flow

1. Create tenant record in Harbor.
2. Issue tenant API key once; store only its hash.
3. Generate a unique Sprite name from the tenant id.
4. Create the Sprite through the Sprites API.
5. Upload the Harbor runtime wheel from the control-plane image into the Sprite.
6. Install the runtime in the Sprite.
7. Create `/workspace/Work/reports` and `/workspace/Work/runs`.
8. Create a checkpoint after the known-good Harbor runtime is installed.
9. Create/authorize provider connector.
10. Attach only the connector metadata to the Harbor tenant.
11. Enable worker and schedule.
12. Execute live connection test.
13. Execute first live worker run.
14. Confirm stored run and output delivery.

No Python source file is edited during customer provisioning.

## Newsletter Intelligence production run

```text
scheduler or API request
        |
        v
claim idempotency key
        |
        v
resolve tenant -> Sprite
        |
        v
write non-secret run spec to Sprite
        |
        v
execute newsletter-intelligence
        |
        v
Sprite calls beehiiv through Fly Connector
        |
        v
real metrics returned
        |
        v
worker derives signals
        |
        v
report written to tenant workspace
        |
        v
result returned to Harbor control plane
        |
        +--> Postgres run record
        +--> email / Slack / MCP result
```

## Security boundary

The control plane is trusted platform code. Worker execution is isolated in the tenant Sprite. Provider credentials are separated again behind connector policy.

For v1:

- one Sprite per tenant;
- private Sprite URL authentication;
- connector access granted only to the intended Sprite or tenant-specific name prefix/labels;
- no provider credentials in Sprite files or env;
- tenant API keys are hashed at rest;
- public API always resolves tenant from authenticated identity;
- remote clients never submit filesystem paths;
- every run has a tenant id, worker id, run id, and idempotency key;
- delete/export paths are part of tenant lifecycle before broad launch.

Before workers are allowed to write/publish externally, Harbor adds explicit capability scopes and approval gates.

## Alex alignment

Alex remains a worker, not the Harbor control plane.

Its target execution path becomes:

```text
Harbor control plane
      |
      v
customer Sprite
      |
      v
reconciled Alex kernel
      |
      +--> Context API (tenant memory/queue/batches/learnings)
      +--> Gate API (persistent quality review)
      +--> client deliverable/output surface
```

The supplied Alex architecture already requires a shared kernel, per-tenant context, persistent gate scoring, surface independence, and a standardized client config. Harbor absorbs the commercial/runtime responsibilities around those pieces instead of rewriting Alex.

## Product surfaces

Harbor's core product is independent of surface.

### HTTP API

Canonical product API. Used by web onboarding, internal admin tooling, and future integrations.

### MCP

Harbor exposes product verbs such as:

- list installed workers;
- get Harbor status;
- run a worker;
- retrieve recent run results;
- install/enable a worker when entitlement allows it.

ChatGPT/Codex connects to this remote authenticated MCP surface. ChatGPT is a surface, not the Harbor host.

### Email / Slack

Delivery adapters consume completed worker results. They do not contain worker logic.

## Deployment topology

### Production v1

- 1 Fly App for Harbor control plane.
- 1 or 2 Fly Machines for the HTTP/API process depending on required redundancy.
- Postgres for control-plane state.
- 1 persistent Sprite per tenant.
- Fly Connectors for tenant provider credentials where supported.
- existing Context API and Gate API remain on their current VPS initially.

### Later

Move Context/Gate only when there is a concrete reliability/operations reason. Do not create migration work before first paying pilots.

## Release path

### v0.9 — infrastructure alpha

- Fly Machine deployable control plane.
- Postgres tenant store.
- tenant API-key auth.
- Sprite provisioner.
- worker dispatch into Sprite.
- real-data-only production behavior.
- manual Fly Connector setup for first beehiiv pilot.

### v0.10 — first paid pilot

- automated scheduler;
- email delivery adapter;
- production Beehiiv connector onboarding;
- first real morning report;
- retry and alerting;
- second tenant isolation test.

### v0.11 — product surface

- remote authenticated MCP server;
- ChatGPT/Codex Skill + MCP packaging;
- simple web onboarding/settings;
- worker enable/disable/install flow;
- run history.

### v0.12 — Alex worker

- reconcile Alex v2.4 live improvements into canonical kernel;
- Context API connection;
- Gate API eight-criterion persistence;
- run Alex inside the same tenant Sprite contract;
- test with second worker enabled in the same tenant environment.

## Definition of "real product"

Harbor is not considered production-ready because a local script works. The first production milestone is complete only when:

1. Harbor has a public HTTPS control-plane URL on Fly.
2. Postgres is the system of record.
3. A tenant can be created without editing source.
4. Harbor creates that tenant's Sprite programmatically.
5. The Sprite contains the current Harbor runtime.
6. A real beehiiv account is connected without storing the raw token in Harbor.
7. A scheduled run pulls real metrics.
8. The report is persisted and delivered.
9. The run appears in Harbor's run store.
10. Re-running the same schedule window cannot duplicate the result/delivery.
11. A second tenant proves isolation.
12. No mock/sample data appears in a production run.

Until all twelve are true, call the build an alpha, not a finished SaaS.
