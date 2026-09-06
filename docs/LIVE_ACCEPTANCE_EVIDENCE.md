# Live acceptance evidence

This file records sanitized production-alpha evidence only. It contains no
tokens, authorization headers, provider credentials, gateway URLs, publication
identifiers, recipient addresses, or customer report content.

## Fly and Sprites pilot

- Harbor control-plane app: `harbor-roger-280`
- Pilot Sprite: `harbor-pilot-07ae38b9`
- Control-plane health: passing
- Postgres schema version: 8
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
They do not make Harbor beta or production-ready; the remaining gates are kept
in `BUILD_STATUS.md`.
