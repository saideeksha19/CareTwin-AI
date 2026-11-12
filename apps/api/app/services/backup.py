from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.utils import iso, new_id


@dataclass(frozen=True)
class BackupResult:
    backup_id: str
    root: Path
    manifest_path: Path
    database_path: Path
    documents_path: Path
    encrypted: bool
    file_count: int
    db_sha256: str


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fernet(key: str | None):
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet  # type: ignore
    except Exception as exc:  # pragma: no cover - dependency/config issue
        raise RuntimeError(
            "Backup encryption requires the cryptography package and a valid Fernet key."
        ) from exc
    return Fernet(key.encode("utf-8") if isinstance(key, str) else key)


def _encrypt_bytes(data: bytes, key: str | None) -> tuple[bytes, bool]:
    f = _fernet(key)
    if f is None:
        return data, False
    return f.encrypt(data), True


def _decrypt_bytes(data: bytes, key: str | None, encrypted: bool) -> bytes:
    if not encrypted:
        return data
    f = _fernet(key)
    if f is None:
        raise RuntimeError("Encrypted backup artifact requires CARETWIN_BACKUP_ENCRYPTION_KEY.")
    return f.decrypt(data)


def _safe_rel(path: Path, root: Path) -> str:
    rel = path.relative_to(root).as_posix()
    if rel.startswith("../") or rel == "..":
        raise ValueError("Unsafe backup path")
    return rel


def create_backup(
    *,
    db_path: Path,
    document_storage_path: Path,
    backup_root: Path,
    encryption_key: str | None = None,
    backup_id: str | None = None,
) -> BackupResult:
    """Create a consistent SQLite backup and a document-storage copy with manifest.

    The source database is backed up using SQLite's online backup API. Document
    files are copied and checksummed. When an encryption key is provided, the
    database backup and each document blob are stored encrypted-at-rest in the
    backup artifact (Fernet, authenticated). Backups are written only under the
    requested backup_root.
    """
    backup_id = backup_id or f"bak_{new_id('')}"  # new_id returns prefix_random; keep readable
    if backup_id.startswith("bak_bak_"):
        backup_id = backup_id.replace("bak_bak_", "bak_", 1)
    root = backup_root / backup_id
    db_out_dir = root / "database"
    docs_out_dir = root / "documents"
    if root.exists():
        raise FileExistsError(f"Backup target already exists: {root}")
    db_out_dir.mkdir(parents=True, exist_ok=False)
    docs_out_dir.mkdir(parents=True, exist_ok=False)

    # Consistent DB snapshot via SQLite backup API.
    raw_db_path = db_out_dir / "caretwin.sqlite3"
    src = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=30.0)
    try:
        dst = sqlite3.connect(str(raw_db_path))
        try:
            src.backup(dst)
            dst.execute("PRAGMA integrity_check").fetchone()
        finally:
            dst.close()
    finally:
        src.close()

    db_bytes = raw_db_path.read_bytes()
    db_plain_sha = hashlib.sha256(db_bytes).hexdigest()
    enc_db_bytes, encrypted = _encrypt_bytes(db_bytes, encryption_key)
    db_artifact = db_out_dir / ("caretwin.sqlite3.enc" if encrypted else "caretwin.sqlite3")
    if encrypted:
        raw_db_path.unlink(missing_ok=True)
    db_artifact.write_bytes(enc_db_bytes)

    manifest_files: list[dict[str, Any]] = []
    file_count = 0
    if document_storage_path.exists():
        for src_file in sorted(p for p in document_storage_path.rglob("*") if p.is_file()):
            rel = _safe_rel(src_file, document_storage_path)
            out_file = docs_out_dir / rel
            out_file.parent.mkdir(parents=True, exist_ok=True)
            plain = src_file.read_bytes()
            plain_sha = hashlib.sha256(plain).hexdigest()
            out_bytes, file_encrypted = _encrypt_bytes(plain, encryption_key)
            artifact_name = rel + (".enc" if file_encrypted else "")
            artifact_path = docs_out_dir / artifact_name
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_bytes(out_bytes)
            manifest_files.append(
                {
                    "relativePath": rel,
                    "artifactPath": artifact_name,
                    "sha256": plain_sha,
                    "sizeBytes": len(plain),
                    "encrypted": bool(file_encrypted),
                }
            )
            file_count += 1

    manifest = {
        "backupId": backup_id,
        "createdAt": iso(),
        "sourceDatabasePath": str(db_path),
        "sourceDocumentStoragePath": str(document_storage_path),
        "encrypted": bool(encrypted),
        "database": {
            "artifactPath": db_artifact.relative_to(root).as_posix(),
            "sha256": db_plain_sha,
            "sizeBytes": len(db_bytes),
            "encrypted": bool(encrypted),
        },
        "documents": {
            "fileCount": file_count,
            "files": manifest_files,
        },
        "formatVersion": 1,
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return BackupResult(
        backup_id=backup_id,
        root=root,
        manifest_path=manifest_path,
        database_path=db_artifact,
        documents_path=docs_out_dir,
        encrypted=bool(encrypted),
        file_count=file_count,
        db_sha256=db_plain_sha,
    )


def verify_backup(*, backup_root: Path, encryption_key: str | None = None) -> dict[str, Any]:
    manifest_path = backup_root / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("Backup manifest not found")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    encrypted = bool(manifest.get("encrypted"))
    db_info = manifest["database"]
    db_artifact = backup_root / db_info["artifactPath"]
    db_bytes = _decrypt_bytes(db_artifact.read_bytes(), encryption_key, bool(db_info.get("encrypted")))
    db_sha = hashlib.sha256(db_bytes).hexdigest()
    if db_sha != db_info["sha256"]:
        raise ValueError("Database backup hash mismatch")
    # integrity check on decrypted sqlite
    tmp = backup_root / ".verify_tmp.sqlite3"
    try:
        tmp.write_bytes(db_bytes)
        conn = sqlite3.connect(str(tmp))
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            if not row or row[0] != "ok":
                raise ValueError("SQLite integrity_check failed")
        finally:
            conn.close()
    finally:
        tmp.unlink(missing_ok=True)

    files = manifest.get("documents", {}).get("files", [])
    for item in files:
        artifact = backup_root / "documents" / item["artifactPath"]
        plain = _decrypt_bytes(artifact.read_bytes(), encryption_key, bool(item.get("encrypted")))
        if hashlib.sha256(plain).hexdigest() != item["sha256"]:
            raise ValueError(f"Document hash mismatch: {item['relativePath']}")
        if len(plain) != int(item["sizeBytes"]):
            raise ValueError(f"Document size mismatch: {item['relativePath']}")
    return {
        "valid": True,
        "backupId": manifest.get("backupId"),
        "encrypted": encrypted,
        "databaseSha256": db_sha,
        "documentCount": len(files),
    }


def restore_backup(
    *,
    backup_root: Path,
    target_db_path: Path,
    target_document_storage_path: Path,
    encryption_key: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Restore a verified backup into explicit target paths.

    This function never touches paths outside the provided targets and refuses to
    overwrite existing targets unless overwrite=True. Callers must ensure targets
    do not point at the live demo database unless explicitly intended.
    """
    verification = verify_backup(backup_root=backup_root, encryption_key=encryption_key)
    manifest = json.loads((backup_root / "manifest.json").read_text(encoding="utf-8"))
    encrypted = bool(manifest.get("encrypted"))

    if target_db_path.exists() and not overwrite:
        raise FileExistsError(f"Target database exists: {target_db_path}")
    if target_document_storage_path.exists() and any(target_document_storage_path.iterdir()) and not overwrite:
        raise FileExistsError(f"Target document storage is not empty: {target_document_storage_path}")

    target_db_path.parent.mkdir(parents=True, exist_ok=True)
    target_document_storage_path.mkdir(parents=True, exist_ok=True)

    db_info = manifest["database"]
    db_bytes = _decrypt_bytes((backup_root / db_info["artifactPath"]).read_bytes(), encryption_key, bool(db_info.get("encrypted")))
    target_db_path.write_bytes(db_bytes)

    for item in manifest.get("documents", {}).get("files", []):
        artifact = backup_root / "documents" / item["artifactPath"]
        plain = _decrypt_bytes(artifact.read_bytes(), encryption_key, bool(item.get("encrypted")))
        out = target_document_storage_path / item["relativePath"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(plain)

    # quick post-restore consistency checks
    conn = sqlite3.connect(str(target_db_path))
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        doc_count = conn.execute("SELECT COUNT(*) FROM medical_documents").fetchone()[0]
    finally:
        conn.close()
    return {
        "restored": True,
        "verification": verification,
        "targetDatabasePath": str(target_db_path),
        "targetDocumentStoragePath": str(target_document_storage_path),
        "integrityCheck": integrity,
        "medicalDocumentRows": doc_count,
    }
