# Harbor v1 architecture

Harbor is a multi-tenant AI worker platform. The production deployment uses a trusted Fly Machine control plane and isolated Fly Sprite computers for tenant execution.

```text
                        SURFACES
        ChatGPT / Codex / Web / Email / Slack
                           |
                           v
                HARBOR CONTROL PLANE
                    Fly Machine
       auth / tenancy / schedules / MCP / API
       worker catalog / run state / routing
                           |
               tenant -> Sprite mapping
                           |
                           v
                 TENANT SPRITE COMPUTER
           persistent workspace + workers
                           |
                  Fly Connector gateway
                           |
                           v
             REAL CUSTOMER DATA SOURCES

        Shared worker services when required:
             Context API / Gate API / LLMs
```

## Separation of concerns

- **Control plane:** tenant/auth/product state, schedules, provisioning, routing, run records, MCP/API.
- **Sprite:** persistent tenant workspace and worker execution.
- **Connector:** external-system access. Secrets remain outside the Sprite wherever Fly Connectors can proxy the provider.
- **Worker:** converts connected data/context into an outcome.
- **Surface:** exposes or delivers worker results; never owns business logic.
- **Postgres:** product system of record, excluding provider secret values.
- **Alex kernel:** shared editorial reasoning/skills installed as a worker after v3 reconciliation.
- **Context API:** durable per-tenant memory/system of record for Alex.
- **Gate API:** persistent quality review for Alex and future quality-gated workers.

## Tenant execution contract

The control plane sends a non-secret run spec into the tenant Sprite. The spec contains tenant metadata, worker id, connection ids/gateway endpoints, worker settings, and input. It never contains provider credentials.

Worker output is written into the persistent tenant workspace and returned as a structured result to the control plane. The control plane persists the run state and dispatches the result to configured surfaces.

## Why Sprites are not the control plane

Sprites are the execution computers. Harbor's public API, authentication, scheduler, and tenant routing need a stable trusted service. That belongs on Fly Machines. Keeping the two separate prevents tenant worker code and generated code from sharing the same trust boundary as Harbor's platform credentials.

## Why one Sprite per tenant first

It gives Harbor a simple isolation model:

- one persistent filesystem;
- one worker environment;
- tenant-scoped connector policies;
- easy checkpoint/restore;
- no need to multiplex customer files into a shared worker computer.

The model can evolve later if economics demand it. Do not optimize away the isolation before product-market evidence exists.
