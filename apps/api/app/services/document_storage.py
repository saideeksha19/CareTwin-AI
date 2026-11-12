from __future__ import annotations

import hashlib
import io
import os
import re
import uuid
from pathlib import Path
from typing import Any

from app.config import Settings
from app.errors import forbidden, validation_error

ALLOWED_DOC_TYPES = {
    "pdf_report",
    "blood_test_report",
    "prescription",
    "discharge_summary",
    "xray_report",
    "mri_ct_report",
    "ultrasound_report",
    "medical_history",
    "consultation_report",
    "follow_up_report",
    "medical_report_image",
    "other_medical_document",
}

EXT_BY_MIME = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/tiff": ".tiff",
    "image/webp": ".webp",
}
MIME_BY_EXT = {v: k for k, v in EXT_BY_MIME.items()}
MIME_BY_EXT[".jpeg"] = "image/jpeg"
MIME_BY_EXT[".tif"] = "image/tiff"

SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def detect_signature_mime(data: bytes) -> str | None:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"II*\x00") or data.startswith(b"MM\x00*"):
        return "image/tiff"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def normalize_filename(name: str) -> str:
    base = os.path.basename(name or "document")
    cleaned = SAFE_NAME_RE.sub("_", base).strip("._") or "document"
    return cleaned[:120]


def ensure_storage_root(settings: Settings) -> Path:
    settings.ensure_paths()
    root = settings.document_storage_path.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def patient_storage_dir(settings: Settings, patient_id: str) -> Path:
    root = ensure_storage_root(settings)
    safe_patient = re.sub(r"[^A-Za-z0-9_-]+", "", patient_id) or "patient"
    path = root / safe_patient
    path.mkdir(parents=True, exist_ok=True)
    return path


def _pdf_page_count(data: bytes) -> int | None:
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(data))
        return len(reader.pages)
    except Exception:
        return None


def validate_upload(
    *,
    settings: Settings,
    patient_id: str,
    filename: str,
    content_type: str | None,
    data: bytes,
    document_type: str,
    max_pdf_pages: int | None = None,
) -> dict[str, Any]:
    if document_type not in ALLOWED_DOC_TYPES:
        raise validation_error(
            "Unsupported document type.",
            {"field": "documentType", "allowed": sorted(ALLOWED_DOC_TYPES)},
        )
    if not data:
        raise validation_error("Uploaded file is empty.", {"field": "file"})
    if len(data) > settings.max_upload_bytes:
        raise validation_error(
            f"File exceeds maximum size of {settings.max_upload_bytes} bytes.",
            {"field": "file", "maxBytes": settings.max_upload_bytes},
        )

    sig_mime = detect_signature_mime(data)
    if not sig_mime:
        raise validation_error("Invalid or unsupported file signature.", {"field": "file"})
    if sig_mime not in settings.allowed_document_mime_types:
        raise validation_error(
            "MIME type is not allowed.", {"field": "file", "detectedMime": sig_mime}
        )

    ext = Path(filename or "").suffix.lower()
    if ext == ".jpeg":
        ext = ".jpg"
    if ext == ".tif":
        ext = ".tiff"
    expected_ext = EXT_BY_MIME[sig_mime]
    allowed_exts = {expected_ext}
    if sig_mime == "image/jpeg":
        allowed_exts.add(".jpeg")
    if sig_mime == "image/tiff":
        allowed_exts.add(".tif")
    if ext and ext not in allowed_exts:
        raise validation_error(
            "File extension does not match detected file signature.",
            {"field": "file", "extension": ext, "detectedMime": sig_mime},
        )

    declared = (content_type or "").split(";")[0].strip().lower()
    # be tolerant of generic browser types but never trust them over signature
    if declared and declared not in {"application/octet-stream", sig_mime, MIME_BY_EXT.get(ext, sig_mime)}:
        raise validation_error(
            "Declared MIME type does not match detected file signature.",
            {"field": "contentType", "declared": declared, "detectedMime": sig_mime},
        )

    page_count = None
    if sig_mime == "application/pdf":
        limit = max_pdf_pages if max_pdf_pages is not None else getattr(settings, "max_pdf_pages", 50)
        page_count = _pdf_page_count(data)
        if page_count is not None and page_count > int(limit):
            raise validation_error(
                f"PDF exceeds maximum page count of {int(limit)}.",
                {"field": "file", "pageCount": page_count, "maxPages": int(limit)},
            )

    safe_original = normalize_filename(filename)
    stored_ext = expected_ext
    stored_filename = f"{uuid.uuid4().hex}{stored_ext}"
    storage_dir = patient_storage_dir(settings, patient_id)
    stored_path = (storage_dir / stored_filename).resolve()
    root = ensure_storage_root(settings)
    if root not in stored_path.parents and stored_path != root:
        raise forbidden("Invalid storage path.")
    return {
        "originalFilename": safe_original,
        "storedFilename": stored_filename,
        "storagePath": str(stored_path),
        "storageRelativePath": str(stored_path.relative_to(root)).replace("\\", "/"),
        "mimeType": sig_mime,
        "extension": stored_ext,
        "fileSizeBytes": len(data),
        "contentHash": hashlib.sha256(data).hexdigest(),
        "pageCount": page_count,
    }


def save_bytes(path_str: str, data: bytes) -> None:
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    # never overwrite; filename is UUID-based
    if path.exists():
        raise validation_error("Storage collision detected; please retry upload.")
    with open(path, "wb") as fh:
        fh.write(data)


def resolve_stored_file(settings: Settings, storage_relative_path: str) -> Path:
    """Resolve a stored document path and enforce containment inside storage root."""
    root = ensure_storage_root(settings)
    abs_path = (root / storage_relative_path).resolve()
    if root != abs_path and root not in abs_path.parents:
        raise forbidden("Invalid document storage location.")
    return abs_path


def verify_integrity(path: Path, expected_sha256: str | None, expected_size: int | None = None) -> bool:
    if not path.exists() or not path.is_file():
        return False
    if expected_size is not None:
        try:
            if path.stat().st_size != int(expected_size):
                return False
        except OSError:
            return False
    if expected_sha256:
        digest = hashlib.sha256()
        try:
            with path.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError:
            return False
        if digest.hexdigest() != expected_sha256:
            return False
    return True
