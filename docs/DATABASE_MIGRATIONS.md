# Database migrations

Harbor applies ordered database migrations when `TenantStore` starts. Applied
versions are recorded in `schema_migrations`; the current expected version is
exposed as `LATEST_SCHEMA_VERSION`.

## Rules

- Add a new immutable migration for every schema change; never edit an applied
  migration.
- Keep SQLite and Postgres migrations behaviorally equivalent.
- Migrations run transactionally. Postgres startup uses an advisory transaction
  lock so only one control-plane Machine migrates at a time.
- CI executes the store contract against both SQLite and an ephemeral Postgres
  service.
- Back up production Postgres before deploying a release with a new migration.
- A migration failure aborts startup. Harbor must not run against a partial or
  unknown schema.

Provider credentials are not database state. Migration code and fixtures may
contain only non-secret connector metadata.
