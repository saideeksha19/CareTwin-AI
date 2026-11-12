# Database Architecture (Phase 15)

## Scope and baseline
- **Local/demo/development engine:** SQLite (WAL mode, `PRAGMA foreign_keys=ON`, `busy_timeout=5000`, per-request connection via `app.db.connect`). The existing synthetic demo database at `data/demo/caretwin.db` is preserved and is not migrated or rewritten by Phase 15.
- **Repository boundary:** API request handling obtains a `Store` (repository) per request in `app/deps.py:get_store`, commits on success, rolls back on exceptions, and always closes the connection. `Store` encapsulates SQL access and patient-scoped queries.
- **Schema initialization:** `app.db.init_db` executes the additive schema DDL, applies safe column backfills, and runs versioned additive migrations recorded in `schema_migrations`.

## Safe, versioned, additive migrations
- Migration registry: table `schema_migrations(id TEXT PRIMARY KEY, applied_at TEXT NOT NULL)`.
- Migrations are **idempotent, additive, and ordered** (`MIGRATIONS` in `app/db.py`). Each step runs once and is recorded; re-running initialization is safe.
- `PRAGMA user_version` is maintained as a monotonic marker (never decremented) for operational visibility.
- **No destructive migrations:** no table drops, no row deletions, no demo-data rewrites. Schema evolution for existing deployments must be performed with additive steps and explicit, reviewed data migrations outside this automated path.
- Phase 15 steps added operational indexes (`idx_documents_patient_uploaded`, `idx_audit_patient_action_time`, `idx_auth_sessions_expires`, `idx_auth_flows_expires`, `idx_guidance_patient_created`) without altering existing rows.

## Transactions, concurrency, and integrity
- SQLite connections enable **foreign keys** and **WAL** journaling; busy timeout reduces transient lock failures.
- Request-scoped commit/rollback in `get_store` ensures failed operations do not partially persist application-level changes within that request boundary.
- Patient ownership/relationship constraints are enforced at the application/repository layer (scoped queries by `patient_id`, access checks, relationship/consent checks) and supported by foreign keys and indexes on patient/document/timeline/audit/session records.
- Concurrent request safety in the demo/local runtime relies on SQLite WAL, short transactions, and busy timeout. Multi-process horizontal scaling requires a server-grade RDBMS (PostgreSQL) and is **not claimed live-verified** in this repository.

## Indexing (frequently queried paths)
Existing and Phase 15 indexes cover:
- Documents/timeline: `idx_documents_patient_time`, `idx_documents_patient_uploaded`, `idx_documents_hash`, `idx_events_patient_time`, `idx_checkins_patient_time`.
- Audit/session: `idx_audit_patient_time`, `idx_audit_patient_action_time`, `idx_auth_sessions_user`, `idx_auth_sessions_expires`, `idx_auth_events_time`, `idx_auth_flows_expires`.
- Extractions/guidance/clinical: `idx_extractions_document`, `idx_extractions_patient`, `idx_extraction_reviews_extraction`, `idx_guidance_patient_time`, `idx_guidance_patient_created`, `idx_evaluations_patient_time`, `idx_labs_patient_time`, `idx_encounters_patient_time`, etc.

## PostgreSQL production strategy (evaluated, not live-migrated)
**Recommendation:** PostgreSQL for production (managed service preferred) to provide robust concurrency, backups/PITR, connection pooling, network isolation, observability, and HA options unavailable to a single-file SQLite deployment.

**Configuration boundary (implemented):**
- `CARETWIN_DATABASE_BACKEND` (`sqlite` default) and `CARETWIN_DATABASE_URL` (empty by default) are defined in settings as the production configuration surface. SQLite remains the **implemented and verified** runtime engine.

**Safe adoption plan (not executed):**
1. Provision PostgreSQL externally (owner/infrastructure action); do not create cloud accounts from this repo.
2. Add/validate a PostgreSQL driver and connection pool (e.g. SQLAlchemy/psycopg or asyncpg) behind a repository/connection abstraction; keep SQL portable or provide dialect-specific migrations.
3. Translate/validate schema and constraints in a **staging database** with synthetic data first; run additive migrations and integrity checks.
4. Export/import data with verified row counts, hashes, and referential integrity; perform cutover only after isolated restore/consistency tests. **Never rewrite the demo SQLite database.**
5. Enable TLS, least-privilege DB roles, automated backups/PITR, and monitoring at the infrastructure layer.

**Current limitations:**
- LIVE VERIFIED WITH REAL SERVICE (PostgreSQL): **not available** (no external database provisioned/tested).
- The repository does not execute PostgreSQL migrations or queries in CI/runtime here; SQLite is the only verified engine.
- Cross-region HA, read replicas, and managed failover are infrastructure-dependent and **NOT IMPLEMENTED** in application code.

## Cross-patient data leakage controls
- Patient-scoped repository methods and access checks require a resolved patient context and authorized relationship/consent.
- Foreign keys tie records to patients/users where applicable; demo data remains synthetic and isolated.
- Backup/restore verification includes patient-scope consistency checks on isolated synthetic restores (see `docs/BACKUP_AND_RECOVERY.md`).
