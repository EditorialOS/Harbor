# Harbor

Harbor is a multi-tenant AI worker platform. A customer creates a workspace,
connects a service, enables a worker, and receives useful work on a schedule.
They do not operate Python, cron, JSON, SSH, or infrastructure.

Newsletter Intelligence is Harbor's first runnable worker. It reads real
beehiiv performance data and produces an editorial brief covering what changed,
why it matters, trends, strongest and weakest content, audience signals,
recommended actions, and anomalies. Alex remains a separate, non-runnable
worker until its v3 reconciliation is complete.

## Architecture

- Harbor's control plane and scheduler run on Fly Machines.
- Postgres is the production system of record.
- Every tenant gets one persistent, private Fly Sprite for worker execution.
- Fly Connectors hold provider credentials and proxy approved API requests.
- ChatGPT, web, email, MCP, and future surfaces are adapters over the same core.

Provider credentials are never stored in Harbor's source, Postgres, tenant
configuration, run specs, reports, logs, or Sprite files. Production failures
are visible and durable; there is no automatic sample-data fallback.

## Current release

`1.0.0-rc.2` is a release candidate, not a production-ready declaration. The
pilot flow has been executed on Fly with Postgres, two isolated Sprites, a real
beehiiv connector, scheduled runs, persisted reports, email delivery, and an
OAuth-authenticated ChatGPT app. See `docs/LIVE_ACCEPTANCE_EVIDENCE.md` for
sanitized evidence and `docs/KNOWN_LIMITATIONS.md` for the remaining launch
gates.

## Local development

Python 3.10 or newer is required.

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[test,production]"
.venv/bin/pytest -q
```

SQLite is used only for local development. Production startup requires
`DATABASE_URL` and uses ordered Postgres migrations. Explicit mock mode is
limited to tests and local development.

## Product surfaces

- Web: passwordless signup, workspace provisioning, source connection,
  scheduling, email delivery, run history, billing, and service status.
- MCP/ChatGPT: authenticated status, worker catalog, latest intelligence,
  sources, recommendations, recent runs, and idempotent worker execution.
- Email: durable, idempotent HTML and plain-text report delivery.
- HTTP API: tenant-scoped product operations and operator provisioning.

## Documentation

- `docs/CUSTOMER_ONBOARDING.md` — customer setup
- `DEPLOY.md` — production deployment
- `docs/OPERATOR_RUNBOOK.md` — normal operations and incident response
- `docs/LAUNCH_CHECKLIST.md` — release gates
- `docs/CHATGPT_SUBMISSION_CHECKLIST.md` — public app submission
- `docs/KNOWN_LIMITATIONS.md` — explicit boundaries
- `docs/SPRITES_LIVE_VERIFICATION.md` — Sprite acceptance checklist
- `docs/PRODUCTION_PLAN.md` — fixed product architecture

Do not enable public paid signup until Stripe, a verified email-sending domain,
external alerts, final legal terms, and the remaining live acceptance checks are
configured and verified.
