# Sprites live verification

This checklist is the credential boundary for `CODEX_NEXT.md` phase 2. Passing
unit tests or building the Docker image does not count as a live Sprites test.

## Verified without external credentials

- The adapter targets the documented `https://api.sprites.dev` API.
- `sprites-py` 0.6 is the only Sprites protocol implementation used by Harbor.
- Sprite creation requests authenticated URL mode with admin-only private access.
- Filesystem upload uses the SDK and preserves the wheel's valid filename.
- Commands use the SDK WebSocket exec implementation.
- Checkpoint NDJSON is consumed through the SDK and must contain a terminal
  `complete` event; an error or incomplete stream fails provisioning.
- Run specs require a Harbor-generated run id and use a unique mode-0600 path.
- Unit contract tests cover response mapping, not-found behavior, idempotent
  create, file upload, exec, and checkpoint failure handling.

## Required live environment

Use a staging Fly organization with Sprites enabled and billing configured. The
operator needs:

- an authenticated `flyctl` session;
- the Sprites CLI authenticated to the same organization;
- an organization-specific Sprites API token capable of creating and operating
  Sprites whose names begin with `harbor-`;
- the built Harbor runtime wheel;
- a staging control-plane app with `SPRITE_TOKEN`, `DATABASE_URL`, and
  `HARBOR_ADMIN_TOKEN` stored as Fly secrets.

Keep the Sprites token in the OS keyring for interactive work and in Fly secrets
for the staging control plane. Never put it in `.env`, shell history, source,
tenant state, a run spec, or a report.

## Live acceptance sequence

1. Confirm `flyctl auth whoami` and `sprite org list` resolve the intended
   staging organization.
2. Deploy the committed Harbor image with a staging Postgres database.
3. Create a staging tenant through the authenticated admin API and retain its
   one-time tenant key in a secret manager.
4. Call `provision-sprite` and confirm Harbor creates the deterministic tenant
   Sprite.
5. Confirm the uploaded Harbor wheel exists in the Sprite and that the installed
   package version matches the control-plane image.
6. Execute a harmless command through Harbor's SDK adapter and confirm stdout,
   stderr, exit status, and non-zero-exit failure behavior.
7. Confirm the runtime-install checkpoint reaches a terminal complete event and
   appears in the Sprite checkpoint list.
8. Write a non-secret persistence probe under `/workspace/Work/runs`, allow the
   Sprite to become cold, then execute another command to wake it and verify the
   probe is unchanged.
9. Run the installed worker entrypoint with a non-secret staging run spec and
   confirm the returned run id matches the Postgres run record and Sprite file.
10. Record sanitized evidence only: Sprite name/id, package version, checkpoint
    id, timestamps, statuses, and content hashes. Do not record tokens, request
    headers, or customer data.

Any mismatch is fixed only in `harbor/sprites_client.py` or
`harbor/sprite_runner.py`; worker code remains infrastructure-independent.
