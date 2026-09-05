---
name: harbor-newsletter-intelligence
description: Use a connected Harbor Newsletter Intelligence worker to retrieve current newsletter performance, interpret recent signals, and return concrete next actions.
---

# Harbor Newsletter Intelligence

Harbor is the source of truth for connected customer metrics. Never invent performance data and never substitute sample metrics when a live Harbor run fails.

## Workflow

1. Confirm Harbor status and that `newsletter-intelligence` is enabled.
2. Run the Newsletter Intelligence worker through the authenticated Harbor MCP app.
3. Read the structured real-data result and current run status.
4. Present the result as a compact operator brief:
   - what happened,
   - what matters,
   - what to do next.
5. If Harbor reports a connection, authorization, or worker failure, report that failure. Do not replace it with generic metrics or fabricated analysis.

## Guardrails

- Treat source metrics as private customer data.
- Never expose connector IDs unnecessarily, provider credentials, platform tokens, or secret references.
- Do not claim causation from a single send; describe observed differences as signals.
- Keep recommendations tied to the metrics Harbor actually returned.
- Publishing or modifying content requires a separate action worker and the relevant approval policy.
