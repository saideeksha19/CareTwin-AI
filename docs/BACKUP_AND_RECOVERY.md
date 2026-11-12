# Backup and Recovery (Phase 15)

## Components
A complete CareTwin recovery requires both:
1. **Database** (SQLite in local/demo): users, patients, relationships, consents, documents metadata, extractions, timeline, alerts, audit events, sessions, AI history, etc.
2. **Document storage** (private local files or production object storage): original uploaded medical documents referenced by database records.

Backups must preserve consistency between database metadata (paths, hashes, sizes, patient ownership) and stored document objects.

## Backup implementation (local, verified)
Implemented in `app.services.backup`:
- **Database backup:** SQLite online backup API (`sqlite3.Connection.backup`) from a read-only source connection to produce a consistent snapshot; `PRAGMA integrity_check` is run on the backup.
- **Document backup:** recursive copy of document files with a manifest entry per file (relative path, SHA-256, size). Storage paths are validated as relative/safe.
- **Manifest:** `manifest.json` records backup id, timestamps, source paths, encryption flag, database hash/size/artifact path, and per-document hashes/sizes/artifacts (`formatVersion: 1`).
- **Optional backup encryption:** if `CARETWIN_BACKUP_ENCRYPTION_KEY` (Fernet key, `cryptography`) is provided, the database backup and each document blob are stored as encrypted artifacts (`*.enc`) using authenticated encryption. Verification/restore require the same key.
- **Retention configuration:** `CARETWIN_BACKUP_RETENTION_COUNT` is defined for operational policy; automated pruning/rotation scheduling is **NOT IMPLEMENTED** as a running job in this repo (operator/cron/task-runner responsibility).

## Integrity verification
`verify_backup`:
- Validates manifest presence and structure.
- Decrypts artifacts when required (fails closed if key missing for encrypted backup).
- Verifies database SHA-256 and runs SQLite `integrity_check` on the restored/decrypted DB image.
- Verifies every document artifact SHA-256 and byte size.

## Restore procedure (isolated/safe)
`restore_backup` restores only into **explicit target paths** provided by the operator/tool:
- Refuses to overwrite existing targets unless explicitly allowed by the caller.
- **Never overwrites the live demo database** (`data/demo/caretwin.db`) or live demo storage during automated tests; tests use isolated synthetic paths.
- Restores DB file, then document files per manifest, then performs post-restore checks (`integrity_check`, document row count) and returns verification details.

**Operator steps (production-like):**
1. Stop writes to the application or place in maintenance mode.
2. Select a verified backup (`verify_backup` must pass).
3. Restore database and document storage to isolated targets; validate application-level consistency (document hashes match files, patient ownership intact, key counts match expectations).
4. Swap/point configuration to restored targets only after validation.
5. Record a backup/restore audit event in operational logs/change records (PHI-free).

## Consistency guarantees
- Document records store `content_hash`, size, and storage-relative path; restore verification confirms file hashes/sizes match the manifest captured at backup time.
- Relationship/metadata integrity is preserved by restoring the consistent DB snapshot and corresponding document set together.
- **Cross-system limitation:** if database and object storage diverge between backup points in a distributed deployment, point-in-time consistency depends on coordinated snapshots/PITR at the infrastructure level (**external dependency, not live-verified here**).

## Backup and restore audit events
- Application audit events are stored in the database; backup/restore operations performed outside request flows should be recorded operationally. A dedicated automated backup-audit hook for external schedulers is **not implemented**; `audit_events` can record operator-initiated actions when run through application tooling.

## Phase 15 verification (isolated synthetic data)
Automated test `apps/api/tests/test_phase15_infra.py::test_backup_verify_and_restore_isolated_synthetic_data`:
- Creates an **isolated synthetic** SQLite DB and synthetic document files (not the demo DB).
- Creates a backup, verifies manifest/hash/integrity, restores to new isolated targets.
- Confirms: DB `integrity_check=ok`, document hashes/sizes unchanged, restored medical-document row present and patient-scoped, source files untouched.
- Additional encrypted-backup test verifies create/verify/restore with a Fernet key.

**Classification:** backup/restore logic and consistency checks are **AUTOMATED TEST VERIFIED / LIVE VERIFIED LOCALLY** on isolated synthetic data. Real off-host/object-store backup pipelines and disaster-recovery drills are **BLOCKED/NOT LIVE-VERIFIED** (no external infrastructure).
