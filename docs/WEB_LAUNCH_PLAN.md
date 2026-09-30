# Harbor web-first launch plan

## Decision

Harbor launches as a standalone web product. The ChatGPT integration remains a
working optional surface for private pilots, but public directory submission is
deferred until customer demand demonstrates that the channel is worth its
additional packaging, review, and maintenance work.

This does not discard the MCP or ChatGPT work. Harbor's product logic remains
surface-independent, so the same account, sources, runs, reports, and approvals
can be exposed through ChatGPT later without redesigning the platform.

## Immediate release path

1. Complete the pilot Kit authorization and verify a real Kit connection.
2. Deploy release candidate 6 and choose Kit as the pilot report source.
3. Run Newsletter Intelligence with real Kit data; inspect the saved report,
   web experience, run record, and retry/error behavior.
4. Complete one unaided new-customer onboarding using the web workspace.
5. Configure a verified email domain and prove delivery to a different customer.
6. Configure Stripe in test mode and prove checkout, portal access,
   cancellation, entitlement changes, and preserved history.
7. Approve final publisher identity, privacy, terms, support, and cancellation
   language.
8. Configure an external alert destination and rehearse database restoration.
9. Tag and deploy the web release, then operate a small paid pilot before
   expanding availability.

## Launch promise

Connect a newsletter. Harbor watches performance and gives you the useful part:
what changed, why it matters, and what to test next.

The customer does not need ChatGPT, a terminal, JSON, SSH, Fly, Sprites, or
Composio knowledge. ChatGPT can be offered as an optional interface for
customers who already work there.

## Local dummy-data proof

Harbor supports explicit development-only mock mode. It never activates
implicitly in production. A local run exercises normalization, analysis,
report generation, state persistence, and run persistence without contacting a
provider or sending email.

Example:

```bash
python -m harbor.cli run-worker newsletter-intelligence \
  --tenant /path/to/local-demo/tenant.json \
  --input mode=mock
```

The generated report clearly identifies itself as mock data. Production stays
fail-closed when a real source cannot be read.

## Deferred distribution track

Revisit public ChatGPT distribution after three to five active pilot customers.
Proceed only if customers repeatedly request ChatGPT access or the directory is
likely to produce qualified demand. Until then, maintain the private ChatGPT
surface as a compatibility check rather than a launch dependency.
