# Harbor v1 web launch checklist

Every required box must be checked with real evidence before Harbor is
described as production-ready or opened to public paid signup. Public ChatGPT
directory distribution is a later, optional channel and is not a web-launch
gate.

## Product

- [x] Newsletter Intelligence uses real data and contains all required analysis
  sections.
- [x] Production has no automatic mock or sample fallback.
- [x] The web workspace covers onboarding, source connection, scheduling,
  output settings, manual runs, recent runs, and activity visibility.
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

## Release

- [x] All tests and the Postgres contract pass on the release commit.
- [x] The release image is deployed and schema 12 is healthy.
- [x] Live report and email delivery pass on the release image.
- [ ] A real Kit connection and report pass on the release image.
- [ ] Git is clean and the release commit/tag is recorded.

## Optional ChatGPT distribution — post-launch

These items improve distribution but do not block the Harbor web product:

- [ ] ChatGPT OAuth and every declared tool pass on the current release image.
- [ ] A private pilot customer confirms that the ChatGPT surface adds value.
- [ ] Public plugin packaging and review materials are updated to OpenAI's
  current submission format.
- [ ] Harbor is submitted for review only after web-product demand is proven.
