# Harbor v1 launch checklist

Every box must be checked with real evidence before Harbor is described as
production-ready or opened to public paid signup.

## Product

- [x] Newsletter Intelligence uses real data and contains all required analysis
  sections.
- [x] Production has no automatic mock or sample fallback.
- [x] ChatGPT app UI covers intelligence, sources, workers, runs,
  recommendations, run control, and connection status.
- [x] Passwordless web onboarding requires no technical setup.
- [ ] A brand-new customer has completed the current release flow unaided.

## Infrastructure and isolation

- [x] Fly app and scheduler Machines pass health checks.
- [x] Postgres is the production system of record.
- [x] Harbor automatically provisions persistent tenant Sprites.
- [x] Two live tenants have distinct auth, Sprites, runs, files, and connector
  policy boundaries.
- [ ] Tenant B has completed its own successful real-source report and delivery.
- [x] `docs/SPRITES_LIVE_VERIFICATION.md` infrastructure checks pass.

## Delivery and operations

- [x] Scheduled execution, bounded retry, idempotency, and durable failure state
  are verified.
- [x] Health, readiness, aggregate metrics, run history, and audit visibility are
  implemented.
- [ ] External alert rules and a monitored destination are configured and fired
  in a test incident.
- [ ] A verified email-sending domain delivers to a new customer address.
- [ ] Backup and restore have been rehearsed against the production database.

## Billing and legal

- [x] Stripe Checkout, webhook verification, entitlements, cancellation gate,
  and customer portal are implemented and locally tested.
- [ ] Stripe products/prices, webhook, portal, and live-mode secret are configured.
- [ ] A real test-mode purchase and cancellation pass end to end.
- [ ] Final privacy policy, terms, support contact, refund/cancellation language,
  and business identity are approved.

## Release and distribution

- [ ] All tests and the Postgres CI contract pass on the release commit.
- [ ] The release image is deployed and schema 12 is healthy.
- [ ] Live report and email delivery pass on the release image.
- [ ] ChatGPT app OAuth and every declared tool pass on the release image.
- [ ] Public ChatGPT app submission materials and review requirements are met.
- [ ] Git is clean and the release commit/tag is recorded.
