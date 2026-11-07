# Vercel preparation and limits

## Included
- `.python-version`: Python 3.12.
- `pyproject.toml`: explicit WSGI entrypoint and build script.
- `vercel.json`: function limit and runtime file exclusions; no legacy all-path redirects or `/api` wrapper.
- PostgreSQL connection via DATABASE_URL, psycopg binary driver and dj-database-url. Local SQLite remains the default when the URL is absent.
- No long-lived database connections (`CONN_MAX_AGE=0`), health checks, disabled server-side cursors for transaction pooling, PostgreSQL connect timeout and required TLS on Vercel.
- Vercel production settings require a generated secret and a PostgreSQL URL. Cloud mode cannot silently create a runtime SQLite database or write `.local-secret`.
- Exact allowed hosts and CSRF origins from VERCEL_URL and VERCEL_PROJECT_PRODUCTION_URL; extra explicit custom domains can be added by environment variables.
- HTTPS redirect, secure session/CSRF cookies and proxy TLS handling enabled only behind Vercel's trusted edge. Existing LAN HTTP behavior stays available locally.
- Migration 0003 creates an operational mutex row. Within each atomic API mutation, PostgreSQL locks that row with SELECT FOR UPDATE **before** reading quantities, statuses or capacities. SQLite continues using BEGIN IMMEDIATE. Both backends intentionally serialize operational writes for this modest course project; this is not a high-throughput architecture.
- PostgreSQL lock waits are bounded by SET LOCAL lock_timeout=8s. Conflicts retain HTTP 409 behavior. The lock is held through commit/rollback, covering allocation, edits, cancellation, receipt confirmation, shelters, approvals and duplicate-safe sync.
- Direct DATABASE_URL_UNPOOLED is used for build migrations when provided. Application traffic keeps its runtime pooled DATABASE_URL.
- The build initializes only the item catalog. Demo users and fictional stock are never automatically seeded on the public site.
- Optional bootstrap credentials create a NEW admin; existing users are never promoted and existing admin passwords are never reset. Remove both username/password bootstrap variables after first success.

## Previews and concurrent builds
Production is intended to deploy from the main branch. Preview deployments fail closed unless RESILIO_PREVIEW_DATABASE_URL is set to a separate isolated database/branch. RESILIO_PREVIEW_DATABASE_URL_UNPOOLED optionally supplies its direct build connection. Production DATABASE_URL is never reused for preview data access. Bootstrap administrator creation is skipped for previews.

Database migration jobs should not be run concurrently against the same database. Use one production deployment at a time. Catalog/bootstrap operations are repeatable and use the operational mutex, but Django's schema migration runner is not a cross-build locking service. For a larger CI pipeline, run migrations as a separately coordinated release job.

## Persistence and access
The hosted PostgreSQL database persists accounts, sessions, notifications and coordination records independently of Vercel function instances. The laptop's SQLite database remains separate; this package does not copy local records or merge separate relief centers. Browser offline queues are origin-specific. A hosted URL needs internet access to its server. For internet-free local-Wi-Fi coordination, continue running the laptop version and use its LAN address.

There is no file upload feature. Static assets are bundled and collected by Vercel; `/sw.js` is served from the included static source. The Cache API still caches an explicit public asset allowlist, not private API responses or presence.

## Validation status
Executed: SQLite workflow suite, cloud catalog/admin bootstrap tests, fresh migrations 0001–0003, local build hook replay, static collection, and subprocess configuration checks for PostgreSQL URL parsing, automatic exact hosts/origins, secure cookies, missing secret/database rejection, refusal of hosted SQLite, preview isolation, wildcard rejection and production DEBUG restrictions. Existing frontend/browser flows are also checked locally.

A live hosted PostgreSQL database and the user's Vercel/GitHub/Neon accounts were not connected in this environment. Native PostgreSQL could not be started under the available process permissions, so PostgreSQL row-lock behavior, pooler connectivity and an actual Vercel deployment are **not claimed as executed tests**. The first hosted deployment must verify connection/migrations and competing reservations before being used beyond a course demonstration.

For a developer with a disposable PostgreSQL server, run the integration suite using DATABASE_URL pointing at that server. Django creates a separate test database; its role must have test-database creation permissions. Never point RESILIO_TEST_DB at real data. The singleton row must be present in test fixtures after transaction-test database flushes.

## Official references checked
- https://vercel.com/docs/frameworks/full-stack/django — automatic manage.py/WSGI detection, build scripts and static collection.
- https://vercel.com/docs/functions/runtimes/python — supported Python runtimes and dependency manifests.
- https://vercel.com/docs/environment-variables/system-environment-variables — exact deployment and production hostname variables.
- https://vercel.com/kb/guide/is-sqlite-supported-in-vercel — local SQLite file persistence is unsuitable for serverless deployment.
