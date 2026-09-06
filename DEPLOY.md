# Harbor — Fly production deployment

This release targets Fly Machines for the Harbor control plane and Fly Sprites for tenant worker computers.

## 0. Prerequisites

You need:

- a Fly.io organization;
- `flyctl` authenticated;
- Sprites enabled for the organization;
- a Sprites API token;
- a Postgres database;
- one real beehiiv publication for the pilot;
- a Fly Custom API Connector for that beehiiv account.

The build can be prepared without these credentials, but a live deployment cannot be completed without them.

## 1. Create the Fly app

Do not embed an app name in source.

```bash
export HARBOR_FLY_APP="your-harbor-app-name"
fly launch --no-deploy --name "$HARBOR_FLY_APP"
```

Keep the generated/selected region as deployment configuration rather than tenant source code.

## 2. Postgres

Provision/attach Postgres and set `DATABASE_URL` on the app. Harbor uses SQLite only for local development.
Harbor applies versioned migrations at control-plane startup and aborts startup
if a migration fails. Back up Postgres before deploying a release with a new
migration; see `docs/DATABASE_MIGRATIONS.md`.

## 3. Platform secrets

Generate a high-entropy admin token and add the Sprites token as Fly app secrets:

```bash
fly secrets set \
  HARBOR_ADMIN_TOKEN='...' \
  SPRITE_TOKEN='...' \
  DATABASE_URL='postgresql://...' \
  -a "$HARBOR_FLY_APP"
```

Do not place customer beehiiv credentials in Fly app secrets. Fly app secrets are app-wide, not tenant connection state.

## 4. Deploy control plane

The Fly configuration defines two process groups: `app` for the HTTP control
plane and `scheduler` for durable scheduled dispatch. Fly runs each group on a
separate Machine. Review the added Machine cost before deploying this release.

```bash
fly deploy -a "$HARBOR_FLY_APP"
```

Verify:

```bash
curl "https://$HARBOR_FLY_APP.fly.dev/healthz"
```

## 5. Create pilot tenant

Use the admin API. The tenant API key is returned once and should be stored in the customer's account/session system. Harbor stores only its hash.

```bash
curl -X POST "https://$HARBOR_FLY_APP.fly.dev/v1/tenants" \
  -H "Authorization: Bearer $HARBOR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "pilot",
    "name": "Pilot Newsletter",
    "timezone": "America/Los_Angeles",
    "workers": ["newsletter-intelligence"],
    "schedule": {"newsletter-intelligence": {"hour": 6, "minute": 0}},
    "outputs": ["files"]
  }'
```

## 6. Provision tenant Sprite

```bash
curl -X POST "https://$HARBOR_FLY_APP.fly.dev/v1/tenants/pilot/provision-sprite" \
  -H "Authorization: Bearer $HARBOR_ADMIN_TOKEN"
```

Harbor creates the Sprite, uploads the exact runtime wheel built into the control-plane release, installs it, creates the persistent workspace, and attempts a checkpoint.

## 7. Connect beehiiv

In Fly Sprites Connectors, create a Custom API connection for the pilot account:

- base URL: beehiiv v2 API;
- credential: the pilot beehiiv API token;
- auth location/prefix matching beehiiv's Bearer token;
- access policy restricted to the pilot Sprite;
- optionally restrict allowed endpoints to the publication/posts endpoints Harbor uses.

Copy the connector's non-secret gateway base URL/id. Attach that metadata to Harbor together with the publication id:

```bash
curl -X POST "https://$HARBOR_FLY_APP.fly.dev/v1/tenants/pilot/connections" \
  -H "Authorization: Bearer $HARBOR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "beehiiv",
    "id": "<connector-id>",
    "gateway_base_url": "<gateway-base-url>",
    "settings": {"publication_id": "<real-publication-id>", "recent_posts": 5}
  }'
```

The raw beehiiv credential is never sent to this Harbor endpoint.

## 8. Run one live worker

```bash
curl -X POST "https://$HARBOR_FLY_APP.fly.dev/v1/tenants/pilot/workers/newsletter-intelligence/run" \
  -H "Authorization: Bearer $PILOT_HARBOR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": {}, "idempotency_key": "pilot-first-live-run"}'
```

A successful production result must not contain mock data.

## 9. Configure and verify scheduling

The tenant can update its worker schedule without source changes. Hours and
minutes are interpreted in the supplied IANA time zone:

```bash
curl -X PUT "https://$HARBOR_FLY_APP.fly.dev/v1/tenants/pilot/workers/newsletter-intelligence/schedule" \
  -H "Authorization: Bearer $PILOT_HARBOR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"hour": 6, "minute": 0, "timezone": "America/Los_Angeles"}'
```

The response includes `next_run_at`. Tenant status exposes the durable next/last
schedule state. The scheduler derives one stable idempotency key per local-date
window, uses bounded retries, and advances directly to the next future window
after downtime.

## 10. What remains before paid pilot

- email output adapter;
- monitoring/alerts;
- connector onboarding UX;
- remote MCP tenant auth;
- second-tenant isolation test.

See `CODEX_NEXT.md` and `docs/PRODUCTION_PLAN.md`.
