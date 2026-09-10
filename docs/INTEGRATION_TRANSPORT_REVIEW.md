# Harbor integration transport review

**Decision date:** September 10, 2026  
**Decision scope:** Pipedream Connect vs Composio as infrastructure behind Harbor  
**Status:** Recommendation ready; no working Harbor integration has been removed

## Executive recommendation

**Adopt Composio selectively, behind a Harbor-owned transport adapter. Do not
adopt Pipedream for Harbor v1. Do not replace the working Beehiiv/Fly Connector
path yet.**

Use Composio first for Kit authentication and authenticated API transport.
Preserve Harbor's current Kit v4 client and normalized adapter, but make its HTTP
transport replaceable. Harbor should call either a direct/Fly transport or a
Composio proxy transport without changing Newsletter Intelligence.

This is a hybrid architecture:

- **Composio:** hosted connection flow, Kit OAuth, token refresh, connection
  lifecycle, and authenticated transport.
- **Fly Connector:** the existing verified Beehiiv API-key path until a staged
  Composio migration proves equal endpoint coverage and reliability.
- **Harbor:** every durable, differentiated product responsibility: tenants,
  Sprites, canonical data, history, time ranges, comparisons, signals,
  schedules, run records, delivery, MCP, and UI.

Pipedream is credible infrastructure, especially when default non-retention of
proxy request and response bodies is the overriding requirement. It is not the
best current fit for Harbor because its official ConvertKit component still
targets the legacy v3 API with an API secret, while Harbor requires current Kit
v4 OAuth and analytics.

## What was verified

### Pipedream

- Connect Link provides a Pipedream-hosted account connection flow. Links are
  scoped to an `external_user_id`, expire after four hours, and can return to
  configured success/error URLs.
- Connected accounts are isolated by external user. One user can connect
  multiple accounts, including multiple accounts for the same app.
- API Proxy makes arbitrary authenticated HTTP requests for an explicit external
  user and connected account. Proxy requests have a 30-second maximum timeout.
- Pipedream stores OAuth grants and key credentials encrypted at rest and manages
  OAuth refresh. Pipedream states that Connect proxy/MCP request and response
  bodies are not persisted.
- Connect actions, MCP calls, trigger deliveries, and proxy requests consume one
  credit per request/execution segment of up to 30 seconds.
- The current Connect plan is $99/month annually, includes 10,000 credits and 100
  external users, charges $2 per additional user, and advertises $0.012 per
  additional credit.
- The official Beehiiv component uses the current `api.beehiiv.com/v2` API-key
  interface. Its app implementation includes publications, posts, subscriptions,
  segments, and aggregate post statistics, although prebuilt action coverage is
  not a complete substitute for Harbor's raw analytics calls.
- The official `convertkit` component still uses `api.convertkit.com/v3` and an
  `api_secret`. Its public actions cover subscribers, forms, and tags, but not the
  current Kit v4 OAuth and analytics surface Harbor needs.
- Pipedream has GA4 report tools, managed authentication, signed connection and
  trigger webhooks, production/development environments, and project-scoped
  rate limits.

### Composio

- Every connection is linked to an application-supplied stable `userID`; private
  connections are usable only by their owner unless deliberately shared.
- Connect Links provide hosted OAuth/API-key collection. Composio manages OAuth
  exchange, token rotation, refresh, and connection-expiry lifecycle events.
- Proxy Execute can call an unwrapped provider endpoint while injecting the
  connected account's credential server-side.
- The current Kit toolkit is versioned `20260721_00`, advertises managed OAuth,
  and exposes 42 tools. Relevant verified tools include Get Account, List
  Subscribers, List Broadcasts, Get Broadcast Stats, Get Email Stats, Get Growth
  Stats, List Tags, and List Segments.
- The Beehiiv toolkit supports API-key authentication and 11 prebuilt tools,
  including publications, posts, subscriptions, and segments. It does not list
  aggregate/post analytics tools, so Harbor would need Proxy Execute for its full
  existing analytics contract. That must be tested before any migration.
- The GA4 toolkit advertises managed OAuth and 69 tools, including Run Report,
  Run Realtime Report, account/property discovery, and metadata.
- Composio signs webhooks and emits both trigger events and connection-lifecycle
  events, including expired accounts.
- Current plans include 100,000 own-app/API-key calls or 20,000 managed-app calls
  on the free tier. Pro costs $29/month with a $29 monthly usage credit. Managed
  app overage is $0.0005/call; proxy execution adds $0.0002/call after its first
  1,000; Zero Data Retention adds $0.0001/call. Up to 1,000 managed connected
  accounts are included; additional managed connections are $0.10 each on paid
  plans.
- Composio retains request/response payloads by default. Zero Data Retention is a
  Pro-or-higher paid add-on. Harbor should require ZDR before production customer
  data passes through Composio.
- Current organization limits are 2,000 requests/minute on Free and 10,000 on
  Pro; Enterprise offers custom limits, KMS, and contractual SLA options.

## A. Current-state Harbor architecture

```text
Human
  -> ChatGPT Harbor app / Harbor web onboarding
  -> Auth0 + Harbor tenant authorization
  -> Harbor control plane on Fly Machines
  -> Postgres tenant/config/run/audit/schedule state
  -> tenant-specific Fly Sprite
  -> Fly custom API connector (Beehiiv credential injection)
  -> Beehiiv API
  -> provider adapter -> canonical newsletter dataset
  -> intelligence, report, run persistence, email, MCP/UI
```

What is real today:

- Authenticated ChatGPT MCP/app access and a minimal editorial Harbor UI.
- Tenant provisioning with one persistent Sprite per tenant.
- Tenant-scoped, idempotent worker dispatch and scheduled runs.
- A live Beehiiv connection using Fly's encrypted custom API connector.
- Provider-neutral newsletter entities and explicit metric-state semantics.
- Beehiiv and Kit v4 normalization adapters.
- Multi-publication portfolio analysis and explicit time windows/comparisons.
- Postgres-backed tenant configuration, run history, audit events, delivery state,
  scheduling state, and health visibility.

What is not yet real:

- A production Kit customer authorization flow and credential refresh path.
- A durable provider-neutral historical observation store independent of run
  payloads.
- A non-newsletter Harbor Data API.
- A staged second-provider live run.

## B. Proposed Composio-assisted architecture

```text
Human -> ChatGPT / Harbor web app
             |
             v
      Harbor identity + tenant
             |
             +---- Connect source ----> Composio Connect Link
             |                              |
             |                         private account
             |                              |
             v                              v
      Harbor control plane            Kit / future OAuth APIs
             |
             v
      tenant-specific Sprite
             |
             v
      Harbor Ingestion Coordinator
             |
             +-- FlyConnectorTransport ----> Beehiiv (existing)
             |
             +-- ComposioTransport --------> Kit (first use)
             |
             v
      Harbor provider normalizer
             |
             v
      Harbor canonical data + history in Postgres
             |
             v
      Harbor Data API -> intelligence -> MCP/UI/email/API
```

The Sprite remains the worker execution boundary. It receives only non-secret
connection metadata: transport type, Harbor connection ID, provider, Composio
connected-account ID, and resource selection. The Composio project API key is a
Harbor platform secret, not tenant configuration or worker input. The exact
mechanism for allowing a Sprite to invoke the proxy must prevent that shared
platform key from being written into the Sprite. The preferred implementation is
a narrow, tenant-authorized Harbor transport endpoint on the control plane; a
Sprite asks Harbor for a fixed provider request, and the control plane calls
Composio after revalidating tenant, connection, method, host, and path.

This preserves tenant Sprites without giving every Sprite a credential that can
access every Composio-connected account.

## C. Keep / replace / simplify audit

| Current Harbor component | Decision | Pipedream capability | Composio capability | Reason | Migration risk |
|---|---|---|---|---|---|
| Auth0 user authentication | Keep | Not a replacement | Not a replacement | Authenticates Harbor users, not provider accounts | Low |
| Tenant/workspace model | Keep | `external_user_id` can mirror tenant | `userID` can mirror tenant | Harbor remains authority; vendor ID is a derived opaque mapping | Medium if IDs are mutable; prohibit that |
| Postgres system of record | Keep | Does not replace canonical Harbor state | Does not replace canonical Harbor state | History and intelligence must survive transport replacement | Low |
| Tenant Sprite provisioning/execution | Keep | Can run workflows, but that changes product architecture | Can run tools/sandboxes, but that changes architecture | Required Harbor isolation/execution model already works | Low |
| Fly Beehiiv connector | Keep for v1 | Could store key and proxy v2 API | Could store key and proxy v2 API | Existing path is verified and cheap; no migration benefit yet | High if replaced before endpoint parity testing |
| Beehiiv raw API client | Keep | Proxy can carry calls | Proxy Execute can carry calls | Pagination, filters, and response semantics are Harbor knowledge | Medium if transport is extracted cleanly |
| Beehiiv normalizer | Keep | No canonical Harbor mapping | No canonical Harbor mapping | Core product/IP | Low |
| Planned Kit OAuth/token refresh/storage | Replace before building | Current official component is legacy v3/API secret | Current Kit toolkit has managed v4 OAuth | Composio eliminates sensitive custom lifecycle code | Medium: vendor auth scopes and production approval must be verified |
| Kit v4 API client | Simplify | Proxy is possible but auth mapping is currently unsuitable | Prebuilt tools plus Proxy Execute cover current endpoints | Retain request/response validation; extract HTTP transport | Medium |
| Kit normalizer | Keep | No Harbor canonical mapping | No Harbor canonical mapping | Core product/IP | Low |
| Provider connection UI | Simplify | Connect Link | Connect Link with basic branding | Replace provider-specific OAuth UI; retain publication/resource selection | Medium |
| Connection verification | Keep + simplify transport check | Connection webhook/account status | Connection status + expiry webhook | Vendor verifies auth; Harbor must verify required resources/metrics | Low |
| Provider resource discovery | Keep | Account/action calls | Toolkit tools/proxy | Harbor decides which publications/resources belong in its model | Low |
| Credential storage | Replace for new OAuth sources | Encrypted managed credentials | Encrypted managed credentials | Reduces Harbor secret surface | Medium vendor dependency |
| Token refresh | Replace for new OAuth sources | Managed | Managed, with expiry event | Commodity infrastructure | Medium vendor dependency |
| Raw authenticated HTTP transport | Make pluggable | API Proxy | Proxy Execute | Prevent vendor logic from entering normalizers/workers | Low if contract is narrow |
| Provider-specific retry | Simplify | Platform behavior plus HTTP errors | Platform behavior plus HTTP errors | Keep Harbor bounded retry/idempotency; remove token-refresh retry | Medium |
| Webhook subscriptions | Defer; vendor-first later | Signed trigger webhooks | Signed triggers + lifecycle webhooks | Useful for freshness, not needed for v1 scheduled reports | Medium |
| Harbor schedules | Keep | Workflow schedules exist | Triggers/schedules exist | Schedules are billable Harbor product behavior and run history | Low |
| Harbor MCP | Keep | Vendor MCP exposes raw actions | Vendor MCP/meta-tools expose raw actions | Harbor must expose clean data, not thousands of provider tools | High if delegated |
| Newsletter Intelligence | Keep | Not provided | Not provided | Core product/IP | Low |
| ChatGPT UI | Keep | Not provided | Not provided | Core product experience | Low |
| Run/audit/delivery visibility | Keep | Vendor logs are supplementary | Vendor logs are supplementary | Harbor owes users one authoritative record | Low |

## D. Estimated development reduction

The current Beehiiv and Kit clients/adapters contain about 985 lines. Most of
those lines are still valuable because they validate, paginate, normalize, and
interpret source data. A managed connection service should not erase them.

Expected reduction from selective Composio adoption:

- **Kit now:** avoid roughly 500–900 lines of OAuth callback, token encryption,
  rotating-refresh-token coordination, database migration, lifecycle recovery,
  and provider-specific onboarding/test code, plus their security tests.
- **Each future OAuth source:** reduce connection/auth development by an estimated
  40–70%; normalizer and capability tests remain.
- **Integration infrastructure overall:** 35–55% less custom auth/transport code,
  not 35–55% less Harbor product code.
- **Schedule for a proven new source:** likely days rather than weeks when the
  vendor has correct endpoint/auth coverage.

These are engineering estimates, not vendor claims. The first Kit staging
integration should be timed and used to recalibrate them.

## E. New capabilities gained

- A nontechnical hosted Kit authorization flow without Harbor handling tokens.
- Automatic token rotation and an explicit connection-expired lifecycle event.
- Faster addition of carefully selected OAuth sources, particularly GA4.
- Authenticated proxy access when a prebuilt action lacks a required endpoint.
- Multiple private connected accounts per tenant/user.
- Connection health and revocation lifecycle independent of a worker run.
- Signed trigger delivery for future incremental ingestion.
- Basic Harbor-branded connection pages without building a provider OAuth UI.

## F. New vendor risks and costs

### Data and security

- Composio is a new subprocesser that sees provider request/response payloads.
- Unlike Pipedream Connect, Composio retains payloads by default. Harbor must use
  the Pro plan with ZDR before production data is routed through it.
- Managed OAuth apps use shared scopes and quotas. Harbor must verify the exact
  Kit scopes and use its own OAuth app later if branding, quota, or scope control
  requires it.
- The Harbor control plane must never expose its Composio project API key to a
  Sprite, browser, model, run spec, report, or tenant database record.

### Reliability and lock-in

- Composio becomes a synchronous dependency for Kit ingestion. If unavailable,
  the run must fail visibly and remain retryable; Harbor must not substitute
  stale or mock data as though the sync succeeded.
- Toolkit schemas are versioned. Harbor should pin a known version and run
  contract tests before advancing it.
- Free/Pro plans have no contractual SLA; an SLA is Enterprise territory.
- Replacing Composio later requires customers to reconnect accounts, but should
  not require changes to the Harbor Data API, canonical schema, intelligence, or
  UI if the transport boundary is respected.

### Cost model

Assumption for comparison: one connected source per customer, one scheduled
daily sync, five authenticated source requests per sync, 30 days/month (150
transport calls per customer), and no trigger events. This is intentionally
simple; multiple sources, more schedules, retries, and proxy-heavy ingestion
increase usage linearly.

| Customers | Calls/month | Pipedream estimate | Composio managed OAuth + Pro ZDR estimate |
|---:|---:|---:|---:|
| 10 | 1,500 | **$99/mo** | **$29/mo** production posture; technically $0 without ZDR |
| 100 | 15,000 | **~$159/mo** ($99 + ~5,000 overage credits) | **$29/mo**; usage fits the included credit/free thresholds |
| 1,000 | 150,000 | **~$3,579/mo** ($1,899 user/platform + ~$1,680 credit overage) | **~$80–$110/mo** depending on prebuilt-tool vs proxy mix, including ZDR |

At 1,000 customers with three managed connected accounts each, Composio adds
about $200/month for the 2,000 connections beyond its first 1,000, before call
usage. Pipedream bills by external user rather than connected-account count, so
extra accounts for one user do not add the $2 user fee, but their calls still
consume credits.

These estimates use the vendors' public September 10, 2026 prices and should be
validated against an actual invoice before Harbor promises margins.

### Infrastructure impact

Potentially eliminated or avoided:

- Harbor-owned OAuth callback/refresh implementation for Kit and similar sources.
- Harbor storage of encrypted provider refresh tokens.
- Provider-specific OAuth connection pages.
- Some low-level connection lifecycle and credential-refresh monitoring.

Still required:

- Fly Machines for the Harbor control plane, scheduler, web app, MCP, and narrow
  authenticated transport broker.
- One Fly Sprite per tenant for v1 worker execution and tenant files.
- Postgres/Supabase for tenants, canonical source data, history, schedules, runs,
  deliveries, audits, and vendor-safe connection metadata.
- Fly Connectors for the working Beehiiv integration and any direct connector
  whose economics/capability justify it.
- Auth0 for Harbor/ChatGPT user authentication.

## G. Recommended migration sequence

1. **Freeze the working Beehiiv path.** Add regression coverage; do not migrate
   the pilot while Kit is being introduced.
2. **Define Harbor's transport boundary.** A provider client asks an injected
   transport for an authenticated request; it never imports Composio/Pipedream.
3. **Define the first generic Harbor Data API contract.** Add only
   `list_sources`, `list_resources`, `get_latest`, `get_history`, `query_period`,
   `compare`, `get_changes`, and `get_signals`, backed by Harbor records—not raw
   vendor tools.
4. **Build Composio in development with ZDR-ready configuration.** Use the tenant
   ID as the immutable Composio `userID`; persist only private connected-account
   IDs and safe status metadata.
5. **Connect one staging Kit account.** Verify scopes, account discovery,
   subscriber totals, growth stats, broadcasts, broadcast stats, tags, date
   filtering, pagination, rate semantics, token refresh, and visible failures.
6. **Run Kit through the existing normalizer and worker.** Prove that no Composio
   object or tool schema leaks into Newsletter Intelligence, Postgres canonical
   records, MCP, or UI.
7. **Test tenant isolation and credential boundaries.** Two tenant IDs, two
   connected accounts, cross-tenant denial, no project key in Sprite state, and
   no raw credential anywhere Harbor persists.
8. **Enable Kit in staging onboarding.** Present one Harbor-branded Connect Link,
   then Harbor resource selection and schedule setup.
9. **Evaluate Beehiiv only after Kit passes.** Compare Fly direct vs Composio
   proxy endpoint parity, latency, failure modes, privacy, and cost. Default to
   keeping Fly unless the simplification is material.
10. **Treat GA4 as the next proof of the generic contract, not as a v1 feature.**
11. **Deploy production only after ZDR and operator monitoring are verified.**

## Harbor Data API boundary

The agent-facing contract should be provider- and transport-neutral:

```python
class HarborDataService(Protocol):
    def list_sources(self, tenant_id: str) -> list[Source]: ...
    def list_resources(self, tenant_id: str, source_ids: tuple[str, ...] = ()) -> list[Resource]: ...
    def get_latest(self, tenant_id: str, resource_ids: tuple[str, ...], metrics: tuple[str, ...]) -> Snapshot: ...
    def get_history(self, tenant_id: str, resource_ids: tuple[str, ...], window: DateWindow) -> History: ...
    def query_period(self, tenant_id: str, query: PeriodQuery) -> Dataset: ...
    def compare(self, tenant_id: str, query: ComparisonQuery) -> Comparison: ...
    def get_changes(self, tenant_id: str, query: ChangeQuery) -> list[Change]: ...
    def get_signals(self, tenant_id: str, query: SignalQuery) -> list[Signal]: ...
```

For v1, Newsletter Intelligence is the only consumer and newsletter is the only
implemented data domain. These method names should not become eight new raw MCP
tools immediately. Harbor can expose a small, task-shaped MCP surface while the
internal contract stabilizes.

## Decision guardrails

- No provider credential or Composio/Pipedream platform key in tenant config,
  Postgres plaintext, logs, reports, run specs, Sprite files, browser code, or
  model context.
- Vendor connected-account IDs are untrusted routing metadata. Harbor always
  checks that an account ID belongs to the current tenant before use.
- Proxy requests use provider-specific allowlists for scheme, host, method, path,
  body size, timeout, and response size. Remote users never provide URLs.
- Pipedream/Composio action results are raw source data, never Harbor's durable
  contract.
- Harbor records every sync outcome and never treats vendor unavailability as a
  successful fresh sync.
- No direct vendor MCP is exposed to ChatGPT users. ChatGPT sees Harbor's clean
  source, history, comparison, and intelligence semantics.

## Official sources

### Pipedream

- [Connect overview](https://pipedream.com/docs/connect)
- [Managed Auth quickstart](https://pipedream.com/docs/connect/managed-auth/quickstart)
- [Connect Link](https://pipedream.com/docs/connect/managed-auth/connect-link)
- [API Proxy](https://pipedream.com/docs/connect/api-proxy)
- [External users and multiple accounts](https://pipedream.com/docs/connect/managed-auth/users)
- [Authentication and scopes](https://pipedream.com/docs/connect/api-reference/authentication)
- [Webhooks](https://pipedream.com/docs/connect/webhooks)
- [Connect rate limits](https://pipedream.com/docs/connect/api-reference/rate-limits)
- [Security and data handling](https://pipedream.com/docs/privacy-and-security)
- [Pricing](https://pipedream.com/pricing)
- [Official Beehiiv app implementation](https://github.com/PipedreamHQ/pipedream/blob/master/components/beehiiv/app/beehiiv.app.ts)
- [Official ConvertKit app implementation](https://github.com/PipedreamHQ/pipedream/blob/master/components/convertkit/convertkit.app.mjs)
- [Official ConvertKit API constants](https://github.com/PipedreamHQ/pipedream/blob/master/components/convertkit/common/constants.mjs)
- [GA4 MCP tool surface](https://mcp.pipedream.com/app/google_analytics)

### Composio

- [Authentication model](https://docs.composio.dev/docs/authentication)
- [Connected accounts](https://docs.composio.dev/reference/api-reference/connected-accounts)
- [Managed OAuth apps](https://docs.composio.dev/toolkits/managed-auth)
- [Proxy Execute](https://docs.composio.dev/reference/v3/api-reference/tools)
- [Webhook subscriptions](https://docs.composio.dev/reference/api-reference/webhook-subscriptions)
- [Kit toolkit](https://docs.composio.dev/toolkits/kit)
- [Beehiiv toolkit](https://docs.composio.dev/toolkits/beehiiv)
- [Google Analytics toolkit](https://docs.composio.dev/toolkits/google_analytics)
- [Rate limits](https://docs.composio.dev/reference/v3/rate-limits)
- [Pricing](https://composio.dev/pricing)
- [Security](https://composio.dev/security/)
- [White-labeling](https://docs.composio.dev/docs/authentication/white-labeling-authentication)

