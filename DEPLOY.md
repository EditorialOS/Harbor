# Harbor production deployment

Harbor runs one HTTP control-plane Machine and one scheduler Machine on Fly.
Postgres is the system of record, and each tenant receives a persistent Fly
Sprite. The same image contains the exact runtime wheel installed in Sprites.

This document deliberately names settings, not their values. Never put a
secret in source, a command transcript, an issue, a report, tenant config, or a
Sprite file.

## External prerequisites

- Fly organization, authenticated `flyctl`, and Sprites enabled
- Sprites organization token
- production Postgres connection with TLS (Fly Managed Postgres or another
  supported hosted Postgres; the current pilot uses Supabase)
- Auth0 tenant, API audience, and regular web application for MCP OAuth
- Resend account and verified sending domain
- Stripe account with three recurring monthly prices, portal, and webhook
- monitored alert destination

## Runtime settings

Set secrets through `fly secrets set -a <app>` or the Fly dashboard. Do not
commit a `.env` file.

Required platform secrets:

| Setting | Purpose |
| --- | --- |
| `DATABASE_URL` | TLS Postgres connection string |
| `SPRITE_TOKEN` | Create and operate tenant Sprites |
| `HARBOR_ADMIN_TOKEN` | Operator-only API authorization |
| `RESEND_API_KEY` | Passwordless login and report email |

Required production configuration:

| Setting | Value or purpose |
| --- | --- |
| `HARBOR_PUBLIC_URL` | Public HTTPS origin, without `/mcp` |
| `HARBOR_EMAIL_FROM` | Sender on the verified Resend domain |
| `HARBOR_SUPPORT_EMAIL` | Public support address shown on `/support` |
| `HARBOR_MCP_OAUTH_REQUIRED` | `true` |
| `HARBOR_MCP_RESOURCE` | Exact public MCP resource URL, without a trailing slash |
| `HARBOR_OAUTH_AUDIENCE` | Same Auth0 API identifier as the MCP resource |
| `HARBOR_OAUTH_ISSUER` | Auth0 tenant HTTPS origin with trailing slash |

Billing stays disabled until every Stripe item below has been verified. Existing
non-billed pilot workspaces remain usable while `HARBOR_BILLING_REQUIRED` is
false.

| Setting | Purpose |
| --- | --- |
| `STRIPE_SECRET_KEY` | Stripe secret-mode API key |
| `STRIPE_WEBHOOK_SECRET` | Signing secret for this endpoint only |
| `STRIPE_PRICE_STARTER` | $29/month recurring Price id |
| `STRIPE_PRICE_GROWTH` | $79/month recurring Price id |
| `STRIPE_PRICE_SCALE` | $199/month recurring Price id |
| `HARBOR_BILLING_REQUIRED` | Set `true` only after the test purchase gate passes |

OpenAI may issue a domain-verification token during public plugin submission.
Set that exact value as `HARBOR_OPENAI_APPS_CHALLENGE`, verify the well-known
endpoint, then leave it in runtime configuration for the reviewed version.

## Release procedure

1. Confirm the launch checklist identifies every unfulfilled external gate.
2. Back up Postgres and record the restore point.
3. Run the complete tests and build checks:

   ```bash
   .venv/bin/pytest -q
   .venv/bin/python -m build
   docker build -t harbor-release-check .
   ```

4. Confirm the intended revision is committed and the Git worktree is clean.
5. Deploy the same revision to the existing Fly app:

   ```bash
   flyctl deploy --app <app-name> --remote-only
   ```

6. Confirm both process groups are healthy, then verify:

   ```bash
   curl -fsS https://<app-name>.fly.dev/healthz
   curl -fsS https://<app-name>.fly.dev/readyz
   curl -fsS https://<app-name>.fly.dev/status
   curl -fsS https://<app-name>.fly.dev/metrics
   curl -fsS https://<app-name>.fly.dev/privacy
   curl -fsS https://<app-name>.fly.dev/terms
   curl -fsS https://<app-name>.fly.dev/support
   ```

7. Confirm an unauthenticated MCP call is rejected, then run an authenticated
   MCP read and one approved worker execution through ChatGPT.
8. Confirm the scheduler heartbeat remains healthy and the resulting run,
   report, and delivery are durable.

Readiness must report the code's current schema version. Migrations are ordered,
transactional, and protected by a Postgres advisory lock. Never bypass a failed
migration. See `docs/DATABASE_MIGRATIONS.md`.

## Stripe configuration and verification

Create three Stripe products/prices matching the published tiers: Starter at
$29/month, Growth at $79/month, and Scale at $199/month. Configure the hosted
Customer Portal. Register `https://<app-name>.fly.dev/stripe/webhook` and select:

- `checkout.session.completed`
- `checkout.session.async_payment_succeeded`
- `checkout.session.async_payment_failed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`

Use Stripe test mode first. Complete Checkout as a new customer, confirm the
signed webhook activates the workspace and provisions exactly one Sprite, open
the hosted portal, cancel, and confirm new scheduled/manual/MCP runs are blocked
while history remains visible. Only then configure live-mode ids/secrets and set
`HARBOR_BILLING_REQUIRED=true`.

Do not advertise the Growth or Scale source limits until the multi-source
product flow has passed its own live acceptance test.

## Customer onboarding behavior

The customer starts at `/signup`, verifies a one-time email code, chooses their
workspace name, time zone, schedule, and delivery email, then completes Stripe
Checkout when billing is enabled. Harbor provisions the Sprite. The customer
pastes the Beehiiv key into Harbor's password field; Harbor passes it directly
to Fly Connectors and persists only non-secret connector metadata.

No customer needs `flyctl`, JSON, SSH, Python, or Sprite access. The older admin
tenant/invitation APIs remain operator recovery tools, not the normal path.

## Rollback and recovery

- Roll back the Fly image only to a revision compatible with the current schema.
- Do not reverse a migration by editing schema-version state.
- Preserve failed run, delivery, billing-event, and audit rows for diagnosis.
- Restore Postgres only from a documented provider restore point after
  preserving the current database and confirming the incident scope.
- Never reuse one tenant's connector or Sprite as a recovery shortcut.

Operational response is in `docs/OPERATOR_RUNBOOK.md`; all release gates are in
`docs/LAUNCH_CHECKLIST.md`.
