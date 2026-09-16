# Known limitations — v1 release candidate

- Public paid signup is intentionally disabled until Stripe production settings,
  a verified sending domain, alerting, and final legal terms are configured.
- The live Resend testing sender can deliver only to the provider account owner;
  customer delivery requires a verified domain.
- Stripe billing is implemented but has not yet been configured or exercised
  against this deployment's Stripe test or live account.
- The second live tenant proved isolation, but its own successful real beehiiv
  report and email delivery still require a second tenant-scoped connection.
- Beehiiv is the only source with a completed live report. Kit normalization,
  OAuth onboarding, and a tenant-scoped Composio transport are deployed, and
  the hosted Kit connection screen is reachable. Consent completion and a real
  Kit report are still pending. The higher plan entitlements are represented,
  but multi-source behavior must be verified before those plans are sold.
- The privacy and terms pages are honest pre-launch placeholders and require
  final business/legal details.
- Aggregate metrics are live, but an external alert destination has not been
  configured and tested.
- The deployment has one HTTP Machine and one scheduler Machine; it is not a
  multi-region or automatic-failover configuration.
- Customer self-service export and deletion are not implemented.
- The ChatGPT app is installed in developer mode and has not been submitted to
  or approved for public directory distribution.
- Alex is intentionally not runnable until its v3 reconciliation.
