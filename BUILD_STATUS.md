# Build status — Harbor 1.0.0 release candidate 6

Harbor's first commercial product loop is implemented. This is a release
candidate, not a production-ready declaration; remaining gates require external
account configuration or a second customer's real data.

## Implemented and locally verified

- Multi-tenant Fly control plane and durable scheduler with Postgres as the
  system of record
- one persistent Fly Sprite per tenant, programmatically provisioned with the
  exact released Harbor runtime
- tenant-restricted Fly Custom API Connectors; no raw provider credential enters
  Harbor state, run specs, logs, reports, or Sprite files
- Newsletter Intelligence using real Beehiiv data, comparative baselines,
  strongest/weakest content, audience/growth signals, anomalies, and actions
- durable tenant/worker-scoped idempotency, bounded retries, expiring leases,
  failed-state persistence, and idempotent report delivery
- passwordless self-service web onboarding, schedule/time-zone controls, email
  settings, source connection, workspace status, runs, and activity audit
- authenticated remote MCP plus a custom ChatGPT UI for latest intelligence,
  sources, workers, recommendations, runs, connection state, and approved runs
- Auth0 OAuth with the authenticated user mapped to exactly one Harbor tenant
- health, readiness, aggregate metrics, public status, security headers, and
  pre-launch privacy, terms, and support pages
- Stripe hosted Checkout and portal, signed/idempotent webhooks, plan
  entitlements, payment gating, cancellation gating, and deferred provisioning
- current customer, operator, deployment, release, limitation, launch, and
  ChatGPT submission documentation

## Live evidence already established

- Fly HTTP and scheduler Machines are running against production Postgres
- the pilot Sprite passed install, checkpoint, cold-wake, persistence, and real
  worker reconciliation checks
- Kit's hosted connection screen is reachable from the pilot workspace;
  consent completion and a real Kit report remain unverified
- a real policy-restricted Beehiiv connector returned customer data only inside
  the pilot Sprite
- a scheduled real-data report completed, persisted, and arrived by email
- Auth0 OAuth connected the Harbor developer-mode ChatGPT app, and Harbor tools
  resolved the workspace from the signed-in user
- a second tenant received a different key, Sprite, run history, and filesystem;
  cross-tenant HTTP access failed and its attempt to use the pilot connector was
  denied by Fly

Sanitized identifiers and results are recorded in
`docs/LIVE_ACCEPTANCE_EVIDENCE.md`.

## External gates still open

- configure Stripe products, prices, portal, and webhook; pass a real test-mode
  purchase and cancellation before enabling paid signup
- verify a Resend sending domain and deliver to a customer address other than the
  provider account owner
- connect the second tenant's own source and complete its real report/delivery
- configure and fire external alert rules against Harbor metrics
- rehearse a production database backup and restore
- replace legal placeholders with approved publisher identity, policies,
  cancellation/refund terms, and public support details
- pass the public OpenAI plugin review checklist and publish after approval

## Deliberately unavailable

- Growth and Scale are not to be sold until multi-source behavior is live-tested
- customer self-service data export/deletion is not implemented
- Alex remains non-runnable until its v3 reconciliation

The authoritative remaining release gates are in `docs/LAUNCH_CHECKLIST.md`.
