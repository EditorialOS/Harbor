# Harbor 1.0.0-rc.1

This release candidate packages Harbor's first commercial product loop without
declaring the service production-ready.

## Included

- Real-data Newsletter Intelligence with comparative analysis and actions.
- Fly Machine control plane and scheduler, Postgres state, and one persistent
  Fly Sprite per tenant.
- Programmatic Sprite provisioning and tenant-restricted Fly Connectors.
- Passwordless customer onboarding and a nontechnical web workspace.
- OAuth-authenticated remote MCP and an editorial ChatGPT app UI.
- Durable scheduled runs, retries, idempotent delivery, audit visibility,
  readiness, metrics, and public aggregate status.
- Stripe hosted Checkout, subscription entitlements, signed idempotent webhooks,
  cancellation gating, and hosted customer portal support.
- Pre-launch privacy/terms pages and operator/customer documentation.

## Verification

Local acceptance is recorded by the repository test suite. Sanitized live
evidence is in `docs/LIVE_ACCEPTANCE_EVIDENCE.md`. Remaining external launch
checks are explicit in `docs/LAUNCH_CHECKLIST.md` and
`docs/KNOWN_LIMITATIONS.md`.
