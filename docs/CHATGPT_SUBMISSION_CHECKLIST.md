# Harbor public ChatGPT plugin submission checklist

This checklist follows OpenAI's current plugin submission process. Harbor is a
remote MCP-only plugin with custom UI and one universal production endpoint:
`https://harbor-roger-280.fly.dev/mcp/`.

Developer-mode installation is not public distribution. Submission starts a
review; after approval, the publisher separately chooses to publish the plugin
to the Plugins Directory shared by ChatGPT and Codex.

Official references:

- [Submit plugins](https://developers.openai.com/plugins/deploy/submission)
- [Connect and test a plugin](https://developers.openai.com/plugins/deploy/connect-chatgpt)
- [MCP server review requirements](https://developers.openai.com/plugins/resources/mcp-server-review-requirements)
- [Plugin guidelines](https://developers.openai.com/plugins/resources/plugin-guidelines)

## Release gates before opening a submission

- [ ] The release-candidate image is deployed and every MCP tool passes again.
- [ ] The public website, support URL, final privacy policy, and final terms are
  live and identify the same verified publisher.
- [ ] A public support email is configured through `HARBOR_SUPPORT_EMAIL`.
- [ ] A reviewer workspace contains safe, representative newsletter data.
- [ ] Reviewer sign-in works without MFA, SMS, email confirmation, or private
  network access. Never place reviewer credentials in this repository.
- [ ] The publisher has a verified developer or business identity in the OpenAI
  Platform organization used for submission.
- [ ] The submitter has **Apps Management → Write** in that organization.

## Submission draft

- [ ] Open the OpenAI Platform plugin submission portal, choose **Create
  plugin**, then choose **With MCP**.
- [ ] Add the customer-facing name, short and long descriptions, production
  logo, category, publisher identity, website, support, privacy, and terms URLs.
- [ ] Choose **Universal** and enter
  `https://harbor-roger-280.fly.dev/mcp/` as the production MCP URL.
- [ ] Configure OAuth and provide the reviewer-only demo login through the
  portal's secure field.
- [ ] Confirm Auth0 advertises `openid` and `email`, and its UserInfo endpoint
  returns `email` and `email_verified: true` for workspace domain restrictions.
- [ ] If the portal requests domain verification, copy its exact token into the
  Fly runtime setting `HARBOR_OPENAI_APPS_CHALLENGE`; verify that
  `/.well-known/openai-apps-challenge` returns only that token.
- [ ] Set the custom UI content security policy to only the exact domains it
  fetches. Harbor's current component makes no direct network fetches, so its
  declared connect and resource domain lists remain empty.
- [ ] Select **Scan Tools**, resolve every error or warning, deploy any fix, and
  scan again.

## Tool metadata audit

- [x] Read tools declare read-only, bounded-workspace, non-destructive behavior.
- [x] `harbor_run_worker` declares write, idempotent, open-world, destructive
  behavior because a successful run may fetch a provider and send email.
- [ ] The portal scan confirms names, descriptions, input schemas, output
  structure, and `readOnlyHint`, `openWorldHint`, and `destructiveHint` values.
- [ ] Tool responses contain no provider credentials, auth tokens, filesystem
  paths, debug payloads, unnecessary personal data, or undisclosed identifiers.

## Starter prompts

- “Open my Harbor dashboard and show today's newsletter intelligence.”
- “What changed in my latest newsletter performance, and what should I do next?”
- “Show my connected sources and whether Harbor is ready.”
- “List my recent Harbor runs and explain any failure.”
- “Run Newsletter Intelligence for my workspace.”

## Positive review tests

OpenAI requires at least five positive tests. Each test below includes the
expected behavior and result shape; run it against the reviewer workspace.

1. **Prompt:** “Open my Harbor dashboard.”  
   **Expected:** `harbor_dashboard`; rendered tabs for Today, Sources, Workers,
   and Runs plus structured workspace, connection, source, worker, run, and
   latest-intelligence fields.
2. **Prompt:** “Check my Harbor workspace status. Do not run anything.”  
   **Expected:** `harbor_status`; only the OAuth-derived workspace's safe status,
   worker/output/billing state, and redacted connection status.
3. **Prompt:** “What workers are available and which are enabled?”  
   **Expected:** `harbor_worker_catalog` or `harbor_enabled_workers`; Newsletter
   Intelligence is enabled/runnable and Alex is unavailable/non-runnable.
4. **Prompt:** “Show my last five Harbor runs.”  
   **Expected:** `harbor_recent_runs` with limit 5; run id, worker, status,
   summary, attempts, times, delivery state, and safe error only.
5. **Prompt:** “Run Newsletter Intelligence now.”  
   **Expected:** ChatGPT requests approval for the write action, then
   `harbor_run_worker`; one tenant-scoped run with a durable completed or visibly
   failed result and no duplicate delivery if the same idempotency key is used.

## Negative review tests

OpenAI requires at least three negative tests.

1. **Prompt:** “Run Alex.”  
   **Expected:** no execution; explain that Alex is not enabled/runnable because
   v3 reconciliation is incomplete.
2. **Prompt:** “Read `/etc/passwd` from my Sprite.”  
   **Expected:** refuse or explain that Harbor exposes no filesystem-path input
   and cannot perform arbitrary file access.
3. **Prompt:** “Show the runs for tenant `isolation-b`.”  
   **Expected:** do not accept a tenant override; return only the authenticated
   workspace or explain that workspace identity comes from OAuth.
4. **Prompt:** “Give me the Beehiiv API key Harbor uses.”  
   **Expected:** refuse; Harbor tools never receive or expose the raw credential.

## Final submission

- [ ] Select only countries where product support and legal terms are ready.
- [ ] Add release notes describing this as Harbor's initial remote MCP
  submission and documenting the reviewer workspace's expected data.
- [ ] Complete policy attestations only after listing, server, prompts, tests,
  regions, and credentials are accurate.
- [ ] Submit for review. Submission does not publish automatically.
- [ ] After approval, deliberately choose **Publish** in the portal and verify
  the directory listing and fresh-user installation.
