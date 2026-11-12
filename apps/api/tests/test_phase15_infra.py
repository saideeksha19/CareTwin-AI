import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect, init_db
from app.main import create_app
from app.services.backup import create_backup, restore_backup, verify_backup
from app.safety.rate_limit import SlidingWindowLimiter
from app.utils import iso


def build_app(tmp_path: Path):
    os.environ["CARETWIN_ENV"] = "test"
    os.environ["CARETWIN_DEMO_MODE"] = "false"
    os.environ["CARETWIN_SEED_DEMO"] = "false"
    os.environ["CARETWIN_DB_PATH"] = str(tmp_path / "app.db")
    os.environ["CARETWIN_DOCUMENT_STORAGE_PATH"] = str(tmp_path / "docs")
    os.environ["CARETWIN_BACKUP_ROOT_PATH"] = str(tmp_path / "backups")
    os.environ.pop("GEMINI_API_KEY", None)
    os.environ.pop("CARETWIN_DOCUMENT_ENCRYPTION_KEY", None)
    os.environ.pop("CARETWIN_BACKUP_ENCRYPTION_KEY", None)
    return create_app()


def seed_synthetic(db_path: Path, docs_root: Path):
    init_db(db_path)
    docs_root.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO users (id,name,role,title,organization,initials,created_at) VALUES (?,?,?,?,?,?,?)",
            ("usr_t", "Test User", "patient", "", "", "TU", iso()),
        )
        conn.execute(
            "INSERT INTO patients (id,mrn,full_name,preferred_name,date_of_birth,sex,primary_language,condition,discharged_on,synthetic,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("pat_t", "MRN-T", "Test Patient", "Test", "1990-01-01", "female", "en", "test", "2026-01-01", 1, iso()),
        )
        conn.execute(
            "INSERT INTO care_relationships (id,patient_id,user_id,relationship,scopes_json,status,created_at) VALUES (?,?,?,?,?,?,?)",
            ("rel_t", "pat_t", "usr_t", "self", json.dumps(["twin:read", "observations:write"]), "active", iso()),
        )
        patient_dir = docs_root / "pat_t"
        patient_dir.mkdir(parents=True, exist_ok=True)
        content = b"%PDF-1.4 synthetic test document"
        rel = "pat_t/synthetic.pdf"
        (docs_root / rel).write_bytes(content)
        sha = __import__("hashlib").sha256(content).hexdigest()
        now = iso()
        conn.execute(
            """INSERT INTO medical_documents (
                id,patient_id,uploaded_by_user_id,uploaded_by_name,uploaded_by_role,
                original_filename,stored_filename,storage_path,document_type,mime_type,
                file_extension,file_size_bytes,content_hash,upload_status,processing_status,
                extraction_status,extraction_method,extraction_error,page_count,is_duplicate_of,
                uploaded_at,processed_at,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "doc_t", "pat_t", "usr_t", "Test User", "patient",
                "synthetic.pdf", "synthetic.pdf", rel, "medical_history", "application/pdf",
                ".pdf", len(content), sha, "stored", "processed",
                "completed", "test", "", 1, None,
                now, now, now, now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {"medical_documents": 1, "sha256": sha, "size": len(content)}


def test_migrations_apply_and_record(tmp_path):
    db = tmp_path / "m.db"
    init_db(db)
    conn = connect(db)
    try:
        rows = conn.execute("SELECT id FROM schema_migrations ORDER BY id").fetchall()
        ids = [r["id"] for r in rows]
        assert "20261111_001_schema_migrations_registry" in ids
        assert "20261111_002_operational_indexes" in ids
        uv = conn.execute("PRAGMA user_version").fetchone()[0]
        assert uv >= 2
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
    finally:
        conn.close()


def test_backup_verify_and_restore_isolated_synthetic_data(tmp_path):
    src_db = tmp_path / "src" / "synthetic.db"
    src_docs = tmp_path / "src" / "documents"
    backup_root = tmp_path / "backups"
    target_db = tmp_path / "restore" / "restored.db"
    target_docs = tmp_path / "restore" / "documents"
    seeded = seed_synthetic(src_db, src_docs)

    result = create_backup(
        db_path=src_db,
        document_storage_path=src_docs,
        backup_root=backup_root,
        backup_id="bak_synthetic",
    )
    assert result.file_count == 1
    assert result.encrypted is False
    verification = verify_backup(backup_root=result.root)
    assert verification["valid"] is True
    assert verification["documentCount"] == 1
    assert verification["databaseSha256"] == result.db_sha256

    restored = restore_backup(
        backup_root=result.root,
        target_db_path=target_db,
        target_document_storage_path=target_docs,
    )
    assert restored["restored"] is True
    assert restored["integrityCheck"] == "ok"
    assert restored["medicalDocumentRows"] == seeded["medical_documents"]

    conn = sqlite3.connect(str(target_db))
    try:
        doc = conn.execute(
            "SELECT patient_id, storage_path, content_hash, file_size_bytes FROM medical_documents WHERE id='doc_t'"
        ).fetchone()
        assert doc is not None
        assert doc[0] == "pat_t"
        assert doc[2] == seeded["sha256"]
        assert doc[3] == seeded["size"]
        patient_scope = conn.execute(
            "SELECT COUNT(*) FROM medical_documents WHERE patient_id!='pat_t'"
        ).fetchone()[0]
        assert patient_scope == 0
    finally:
        conn.close()

    restored_file = target_docs / "pat_t" / "synthetic.pdf"
    assert restored_file.exists()
    assert __import__("hashlib").sha256(restored_file.read_bytes()).hexdigest() == seeded["sha256"]
    # source untouched
    assert (src_docs / "pat_t" / "synthetic.pdf").exists()


def test_backup_restore_with_encryption_key(tmp_path):
    key = "3Q3YwzXH8r7v2mYtP0LqKkW9oS8dN1eFv4aBcDeFgHI="  # 32-byte urlsafe base64 Fernet key
    src_db = tmp_path / "src" / "synthetic.db"
    src_docs = tmp_path / "src" / "documents"
    backup_root = tmp_path / "backups"
    target_db = tmp_path / "restore" / "restored.db"
    target_docs = tmp_path / "restore" / "documents"
    seeded = seed_synthetic(src_db, src_docs)
    result = create_backup(
        db_path=src_db,
        document_storage_path=src_docs,
        backup_root=backup_root,
        encryption_key=key,
        backup_id="bak_enc",
    )
    assert result.encrypted is True
    assert (result.root / "database" / "caretwin.sqlite3.enc").exists()
    verification = verify_backup(backup_root=result.root, encryption_key=key)
    assert verification["valid"] is True
    restored = restore_backup(
        backup_root=result.root,
        target_db_path=target_db,
        target_document_storage_path=target_docs,
        encryption_key=key,
    )
    assert restored["integrityCheck"] == "ok"
    assert __import__("hashlib").sha256((target_docs / "pat_t" / "synthetic.pdf").read_bytes()).hexdigest() == seeded["sha256"]


def test_health_and_ready_endpoints(tmp_path):
    app = build_app(tmp_path)
    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        body = health.json()
        assert body["status"] in {"ok", "degraded"}
        assert body["database"] == "connected"
        assert "components" in body
        assert body["components"]["database"]["status"] == "ok"
        assert body["components"]["storage"]["status"] == "ok"
        assert body["components"]["authentication"]["mode"] == "demo"

        ready = client.get("/api/v1/ready")
        assert ready.status_code == 200
        rbody = ready.json()
        assert rbody["ready"] is True
        assert rbody["components"]["database"]["engine"] == "sqlite"
        assert rbody["components"]["rateLimiting"]["backend"] == "memory"
        assert rbody["components"]["rateLimiting"]["sharedStoreConfigured"] is False


def test_rate_limiter_backend_and_limits():
    limiter = SlidingWindowLimiter(backend="memory")
    assert limiter.backend == "memory"
    assert limiter.is_shared_store is False
    for _ in range(3):
        limiter.hit("test", "u1", 3, window_seconds=3600)
    try:
        limiter.hit("test", "u1", 3, window_seconds=3600)
        assert False, "expected rate limit"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 429
    shared = SlidingWindowLimiter(backend="redis")
    assert shared.is_shared_store is True
