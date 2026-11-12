# Storage Security (Phase 15)

## Objectives
Protect uploaded medical documents (PHI-adjacent synthetic demo content in this repo; treat all medical documents as sensitive) through strict validation, private storage, per-patient isolation, integrity controls, and authorized retrieval only.

## Implemented controls (local private storage, verified locally)

### Storage abstraction and layout
- **Backend:** local private filesystem storage (`CARETWIN_STORAGE_BACKEND=local`, `CARETWIN_DOCUMENT_STORAGE_PATH`, default `data/documents`). The API layer stores/retrieves documents via `app.services.document_storage` helpers; filesystem paths are not exposed in API responses.
- **Production-compatible adapter strategy:** configuration surface supports a future private object-storage backend (`storage_backend`, bucket/prefix settings). A live cloud object-storage adapter is **not implemented/verified** in this environment; no public buckets or unauthenticated URLs are permitted by design.
- **Per-patient isolation:** files are stored under a sanitized per-patient directory. Storage keys are UUID-based filenames (no user-controlled path components in stored names).
- **Original preservation:** uploaded bytes are stored as received (after validation) with immutable UUID storage names; duplicate content is detected by hash and flagged while preserving upload records safely.

### Upload validation and limits
- **MIME/extension/signature validation:** detected from file signature (magic bytes) for PDF, PNG, JPEG, TIFF, WEBP; extension and declared content type must be consistent with the detected signature. Unsupported or mismatched files are rejected.
- **Size limit:** `CARETWIN_MAX_UPLOAD_BYTES` (default 15 MB).
- **PDF page-count limit:** `CARETWIN_MAX_PDF_PAGES` (default 50) enforced during validation when page count is detectable (`pypdf`). Oversized PDFs are rejected.
- **Path traversal protection:** stored paths are resolved and must remain within the storage root (`resolve_stored_file` containment checks); patient directory names are sanitized.
- **No overwrite on collision:** UUID-based naming prevents accidental overwrite; collisions fail safely.

### Integrity and retrieval
- **Cryptographic integrity:** SHA-256 content hash recorded per document; storage helpers provide integrity verification (`verify_integrity`) against expected hash/size. Backup/restore verifies hashes and sizes for every document artifact.
- **Secure retrieval:** documents are served only through authenticated, authorized API endpoints (patient/relationship/role checks). Responses use private/no-store headers and `X-Content-Type-Options: nosniff`; no public document URLs are generated.
- **Short-lived authorized download:** not implemented as a separate signed-URL mechanism for local storage; access is mediated by the API/session/bearer authorization on each request. For a future object-storage backend, downloads must use short-lived, scoped, authenticated URLs/tokens only (not implemented live).

### Storage failure handling
- Upload/storage failures are surfaced as validation/processing errors without exposing internal paths or secrets.
- Processing errors are recorded on document state; failed operations roll back request-scoped DB changes where applicable.

## Encryption at rest (documents)
- **Implemented/configurable:** application-level document encryption hooks are **partially prepared** via configuration (`CARETWIN_DOCUMENT_ENCRYPTION_KEY`, `CARETWIN_REQUIRE_DOCUMENT_ENCRYPTION`) and backup-artifact encryption using Fernet (authenticated encryption, `cryptography`). **Live document-at-rest encryption in the primary storage path is not fully enabled by default** in this phase to avoid breaking existing demo document reads without a coordinated migration.
- **Fail-closed intent:** in production mode, missing required document-encryption configuration is reported as a configuration issue (`production_config_issues`) when `CARETWIN_REQUIRE_DOCUMENT_ENCRYPTION=true`; operators must supply a valid key before claiming encrypted storage.
- **Key management:** keys must be provided via environment/secret store, never hardcoded, never logged, and rotated according to `docs/BACKUP_AND_RECOVERY.md`/deployment policy. Key rotation for existing encrypted blobs requires a controlled re-encryption process (**planned, not automated here**).
- **Honest limitation:** unless document-level encryption is explicitly enabled, verified, and migrated for all stored objects, **do not claim all stored medical documents are encrypted at rest** beyond underlying disk/infrastructure protections.

## What is not claimed
- Public/private cloud object storage live integration: **NOT LIVE VERIFIED** (no credentials/services).
- Customer-managed KMS/HSM integration: **NOT IMPLEMENTED**.
- Automatic key rotation/re-encryption of historical documents: **NOT IMPLEMENTED**.
- End-to-end encryption between browser and storage independent of HTTPS: **NOT IMPLEMENTED** (transport security is an infrastructure/HTTPS concern).

## Safe operational guidance
- Keep `data/documents` and backups private to authorized system users/processes.
- Exclude secrets and sensitive paths from logs and error responses.
- Treat all document content, filenames, and extracted medical text as sensitive in logs/monitoring (see health endpoints: no internal paths or PHI exposed).
