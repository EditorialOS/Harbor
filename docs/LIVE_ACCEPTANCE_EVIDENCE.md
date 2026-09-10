# Live acceptance evidence

This file records sanitized live evidence only. It contains no
tokens, authorization headers, provider credentials, gateway URLs, publication
identifiers, recipient addresses, or customer report content.

## Fly and Sprites pilot

- Harbor control-plane app: `harbor-roger-280`
- Pilot Sprite: `harbor-pilot-07ae38b9`
- Control-plane health: passing
- Postgres schema version: 12
- Sprite runtime install, checkpoint, cold wake, persistent probe, and live
  worker reconciliation: passed using `docs/SPRITES_LIVE_VERIFICATION.md`

## Operational health

- Fly HTTP health check uses database-aware `/readyz`: passing
- Fly Prometheus scrape endpoint: live
- Scheduler durable heartbeat: healthy
- Overdue schedule count at verification: zero
- Expired run lease count at verification: zero
- Metrics expose aggregate counts without tenant identifiers: passed
- External alert destination and alert rules: not yet configured

## Authenticated web surface

- Public landing page: HTTP 200
- Existing pilot key exchanged for a hashed browser session: HTTP 303
- Authenticated pilot workspace: HTTP 200
- Pilot connection health and run history: visible
- Second-tenant identifier in pilot workspace response: absent
- Provider-credential and filesystem-path input fields: absent
- Invite redemption, session hashing, CSRF, automatic provisioning, and failure
  persistence: covered by local and PostgreSQL contract tests

## Scheduled and delivered live job

- Scheduled live run: `run_0eb3300cc788fbb9e10fa295`
- Scheduled run status: completed on first attempt
- Next scheduled window recorded in Postgres: `2026-09-07T13:00:00+00:00`
- Render-verification run: `run_51d143d8dc1a0799dea0de91`
- Durable delivery: `delivery_41c03257bee2736e9320d09c`
- Delivery status: delivered on first attempt
- Inbox rendering: visibly confirmed
- Production mock marker: absent
- Resend secret in tenant/run/report state: absent

## v1 release-candidate deployment

- Deployed package version: `1.0.0rc2`
- Fly app and scheduler Machine version: 22
- Fly image: `deployment-01M247MKCF1DS38J6ZB3CVFZTB`
- Database schema version: 12
- `/healthz`, `/readyz`, `/status`, `/metrics`, `/privacy`, `/terms`,
  `/support`, and `/signup`: passed
- MCP protected-resource OAuth discovery: passed
- Unauthenticated MCP request: HTTP 401
- Auth0 discovery advertises authorization, token, UserInfo, registration,
  `openid`, `email`, and `offline_access`: passed
- Release-check run: `run_ca640a049e9934b6a3ba72f3`
- Existing pilot Sprite automatically upgraded to the bundled runtime
  fingerprint before execution: passed
- Real-source worker and email delivery: completed on first attempt
- Required analysis sections in the persisted Sprite report: all present
- Persisted report bytes: 1,385
- Persisted report SHA-256:
  `800e4766e2c2defe92a9e34a4312bf509985ac0466fc02b8171bb2229089f42c`
- Production mock marker: absent
- Repeating the release-check idempotency key: duplicate suppressed
- Local complete suite with disposable PostgreSQL 16: 104 passed
- Local and Fly remote production image builds: passed
- ChatGPT selected and mounted the `harbor_dashboard` MCP Apps resource: passed
- The first live dashboard render exposed a missing MCP Apps initialization
  handshake; the standards-compliant handshake is deployed in rc.2 and awaits
  a refreshed live ChatGPT render check.

## Second-tenant isolation

- Second tenant: `isolation-b`
- Second Sprite: `harbor-isolation-b-c1f8d8ae`
- Sprite names differ: passed
- Pilot key against second-tenant HTTP route: 401
- Second-tenant key against pilot HTTP route: 401
- MCP auth-derived tenant identity: passed
- Run-id intersection between tenant-visible histories: zero
- Cross-Sprite file probes in both directions: not found
- Pilot Sprite access to pilot beehiiv connector: HTTP 200
- Second Sprite access to pilot beehiiv connector: HTTP 403
- Missing-connector worker failure persisted for tenant B: passed

These results complete the first delivered-pilot and live isolation milestones.
They do not make Harbor production-ready; the remaining gates are kept
in `BUILD_STATUS.md`.
