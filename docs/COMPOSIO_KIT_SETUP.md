# Composio Kit setup and live verification

Kit is disabled by default. These steps activate the already-implemented
Composio transport without moving Harbor's product logic, tenant state, or
worker execution out of Harbor and Fly Sprites.

Never paste a Composio project key into chat, source, tenant configuration,
Postgres, a run record, or a Sprite. Store it only as a Fly application secret.

## Architecture and safety gates

- Composio hosts Kit OAuth and stores/refreshes the provider grant.
- The Composio project key exists only on Harbor's control-plane Machine.
- A Sprite receives a one-hour maximum Harbor grant scoped to one tenant, one
  Harbor source, one provider, and one run. The broker also requires that run's
  database lease to remain active. Its transient run-spec file is removed after
  execution.
- The public broker accepts five read-only Kit operations: account,
  subscribers, growth statistics, broadcast statistics, and tags.
- Harbor revalidates the signed tenant and stable Harbor source mapping before
  every proxied request.
- No Composio MCP or raw toolkit actions are exposed to ChatGPT users.
- Composio Zero Data Retention and callback identity verification are required;
  the source UI stays disabled until both are explicitly confirmed.

## One-time Composio project setup

1. Create or select the production Harbor project in Composio Platform.
2. Use a Pro-or-higher plan and enable Zero Data Retention for the project.
3. Create an Auth Config for the **Kit** toolkit using Composio-managed OAuth.
   Record the non-secret Auth Config ID.
4. Under the project's callback identity verification setting, save exactly:

   `https://<harbor-app>.fly.dev/app/connections/composio/verify`

5. Create a scoped project API key with only the access Harbor needs:
   Connected Accounts read/write and Proxy Execute write. Copy it directly to
   the Fly secret form; do not save or send it elsewhere.
6. Generate a separate random broker-signing value of at least 32 bytes and
   store it directly as a Fly secret.

Set these on the existing Harbor Fly app:

```text
COMPOSIO_API_KEY
HARBOR_COMPOSIO_KIT_AUTH_CONFIG_ID
HARBOR_BROKER_SIGNING_KEY
HARBOR_COMPOSIO_ZDR_CONFIRMED=1
HARBOR_COMPOSIO_CALLBACK_VERIFICATION_CONFIRMED=1
```

`HARBOR_PUBLIC_URL` must already be the Harbor HTTPS origin. After the settings
are saved, deploy the candidate to staging before production.

## Staging acceptance checklist

- [ ] The Harbor workspace shows **Connect Kit** only after all safety settings
  are present.
- [ ] A new staging tenant starts the link from its authenticated Harbor page.
- [ ] Kit consent returns through Harbor's callback identity verifier.
- [ ] Harbor stores a stable `kit-...` source ID and non-secret vendor account
  ID, but no OAuth token or API key.
- [ ] A second tenant cannot use, view, or replace the first tenant's Kit source.
- [ ] A manual Newsletter Intelligence run executes inside the correct tenant
  Sprite and reads real Kit v4 data.
- [ ] The normalized report distinguishes unavailable/unsupported data from
  measured zero values.
- [ ] The run, report, and delivery are persisted for only that tenant.
- [ ] An expired/tampered Harbor broker grant is rejected.
- [ ] A request for an unapproved operation or query parameter is rejected
  before Composio is called.
- [ ] Disabling Composio or Kit produces a visible persisted failure, never a
  sample or stale-data success.
- [ ] The existing real Beehiiv/Fly Connector run still passes unchanged.

Do not call Kit live or sell multi-source plans until every item above has real
staging evidence. If the check fails, remove either confirmation setting to
hide Kit immediately without affecting Beehiiv.
