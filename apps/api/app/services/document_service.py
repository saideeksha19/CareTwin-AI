from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import Request

from app.config import Settings
from app.domain.schemas import DocumentReviewRequest, GuidanceRequest
from app.errors import forbidden, not_found, validation_error
from app.repositories.store import Store
from app.services import document_analysis, document_extraction, document_storage, twin_service
from app.services.auth import require_access, require_clinician
from app.utils import iso, new_id


def _doc_dto(doc: dict[str, Any], *, include_private: bool = False) -> dict[str, Any]:
    dto = {
        "id": doc["id"],
        "patientId": doc["patient_id"],
        "originalFilename": doc["original_filename"],
        "documentType": doc["document_type"],
        "mimeType": doc["mime_type"],
        "fileExtension": doc["file_extension"],
        "fileSizeBytes": doc["file_size_bytes"],
        "contentHash": doc.get("content_hash") or "",
        "uploadStatus": doc.get("upload_status") or "stored",
        "processingStatus": doc.get("processing_status") or "uploaded",
        "extractionStatus": doc.get("extraction_status") or "pending",
        "extractionMethod": doc.get("extraction_method") or "",
        "extractionError": doc.get("extraction_error") or "",
        "pageCount": doc.get("page_count"),
        "isDuplicateOf": doc.get("is_duplicate_of"),
        "uploadedAt": doc.get("uploaded_at"),
        "processedAt": doc.get("processed_at"),
        "uploadedBy": {
            "id": doc.get("uploaded_by_user_id"),
            "name": doc.get("uploaded_by_name") or "",
            "role": doc.get("uploaded_by_role") or "",
        },
    }
    # never expose storage_path publicly
    return dto


def _page_dto(page: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": page["id"],
        "documentId": page["document_id"],
        "pageNumber": page["page_number"],
        "extractionMethod": page.get("extraction_method") or "",
        "status": page.get("status") or "pending",
        "error": page.get("error") or "",
        "textContent": page.get("text_content") or "",
    }


def _extraction_dto(item: dict[str, Any], reviews: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "id": item["id"],
        "documentId": item["document_id"],
        "patientId": item["patient_id"],
        "itemType": item["item_type"],
        "label": item["label"],
        "valueText": item.get("value_text") or "",
        "valueNumeric": item.get("value_numeric"),
        "unit": item.get("unit") or "",
        "referenceRange": item.get("reference_range") or "",
        "abnormalFlag": item.get("abnormal_flag") or "",
        "pageNumber": item.get("page_number"),
        "sourceText": item.get("source_text") or "",
        "extractionStatus": item.get("extraction_status") or "extracted",
        "verificationStatus": item.get("verification_status") or "unverified",
        "confidenceNote": item.get("confidence_note") or "",
        "evidenceId": item.get("evidence_id"),
        "verifiedBy": {
            "id": item.get("verified_by_user_id"),
            "name": item.get("verified_by_name"),
            "at": item.get("verified_at"),
        },
        "rejectedBy": {
            "id": item.get("rejected_by_user_id"),
            "name": item.get("rejected_by_name"),
            "at": item.get("rejected_at"),
        },
        "reviewNote": item.get("review_note") or "",
        "correctedValueText": item.get("corrected_value_text"),
        "original": json.loads(item.get("original_payload_json") or "{}"),
        "reviews": [
            {
                "id": r["id"],
                "action": r["action"],
                "actorName": r["actor_name"],
                "actorRole": r["actor_role"],
                "previousVerificationStatus": r["previous_verification_status"],
                "newVerificationStatus": r["new_verification_status"],
                "previousValue": json.loads(r.get("previous_value_json") or "{}"),
                "newValue": json.loads(r.get("new_value_json") or "{}"),
                "note": r.get("note") or "",
                "createdAt": r["created_at"],
            }
            for r in (reviews or [])
        ],
        "createdAt": item.get("created_at"),
        "updatedAt": item.get("updated_at"),
    }


def _get_patient_doc(store: Store, user: dict[str, Any], patient_id: str, document_id: str, scope: str = "twin:read"):
    access = require_access(store, user, patient_id, scope)
    doc = store.get_document(patient_id, document_id)
    if not doc:
        raise not_found("Medical document")
    return access, doc


async def parse_multipart_upload(request: Request) -> tuple[bytes, str, str, dict[str, str]]:
    """Minimal multipart parser (fallback when python-multipart unavailable)."""
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise validation_error("Expected multipart/form-data upload.")
    # boundary
    boundary = None
    for part in content_type.split(";"):
        part = part.strip()
        if part.lower().startswith("boundary="):
            boundary = part.split("=", 1)[1].strip().strip('"')
            break
    if not boundary:
        raise validation_error("Missing multipart boundary.")
    body = await request.body()
    marker = ("--" + boundary).encode()
    sections = body.split(marker)
    file_bytes = b""
    filename = ""
    file_ct = ""
    fields: dict[str, str] = {}
    for sec in sections:
        if not sec or sec in (b"--\r\n", b"--", b"\r\n"):
            continue
        sec = sec.lstrip(b"\r\n")
        if sec.endswith(b"--\r\n"):
            sec = sec[:-4]
        if sec.endswith(b"--"):
            sec = sec[:-2]
        if b"\r\n\r\n" not in sec:
            continue
        head, data = sec.split(b"\r\n\r\n", 1)
        if data.endswith(b"\r\n"):
            data = data[:-2]
        headers = head.decode("utf-8", errors="ignore")
        name_match = re_search(headers, r'name="([^"]+)"')
        fname_match = re_search(headers, r'filename="([^"]*)"')
        ctype_match = re_search(headers, r"Content-Type:\s*([^\r\n]+)", flags=re.IGNORECASE)
        name = name_match.group(1) if name_match else ""
        if fname_match and fname_match.group(1):
            filename = fname_match.group(1)
            file_bytes = data
            file_ct = ctype_match.group(1).strip() if ctype_match else ""
        elif name:
            fields[name] = data.decode("utf-8", errors="ignore")
    if not filename and not file_bytes:
        raise validation_error("No file provided in upload.", {"field": "file"})
    return file_bytes, filename, file_ct, fields


def re_search(text, pattern, flags=0):
    import re
    return re.search(pattern, text, flags)


def upload_document(
    store: Store,
    settings: Settings,
    *,
    user: dict[str, Any],
    patient_id: str,
    filename: str,
    content_type: str | None,
    data: bytes,
    document_type: str,
) -> dict[str, Any]:
    access = require_access(store, user, patient_id, "clinical:write" if user["role"] == "clinician" else "observations:write")
    # allow patient/caregiver/clinician uploads within their access; but keep strict patient association
    if user["role"] not in {"patient", "caregiver", "clinician"}:
        raise forbidden("Not authorized to upload documents.")
    meta = document_storage.validate_upload(
        settings=settings,
        patient_id=patient_id,
        filename=filename,
        content_type=content_type,
        data=data,
        document_type=document_type,
        max_pdf_pages=getattr(settings, "max_pdf_pages", 50),
    )
    now = iso()
    duplicate = store.find_document_by_hash(patient_id, meta["contentHash"])
    doc_id = new_id("doc")
    # store file safely (preserve original file). For duplicate content, still store a new file record? safer to avoid duplicate stored content but keep record; however "handle duplicate uploads safely"
    # We save bytes for this upload to preserve the original uploaded file instance; duplicate is flagged.
    try:
        document_storage.save_bytes(meta["storagePath"], data)
    except Exception as exc:
        raise validation_error(f"Failed to store uploaded file: {exc}")

    doc = {
        "id": doc_id,
        "patient_id": patient_id,
        "uploaded_by_user_id": user["id"],
        "uploaded_by_name": user["name"],
        "uploaded_by_role": user["role"],
        "original_filename": meta["originalFilename"],
        "stored_filename": meta["storedFilename"],
        "storage_path": meta["storageRelativePath"],
        "document_type": document_type,
        "mime_type": meta["mimeType"],
        "file_extension": meta["extension"],
        "file_size_bytes": meta["fileSizeBytes"],
        "content_hash": meta["contentHash"],
        "upload_status": "stored",
        "processing_status": "uploaded",
        "extraction_status": "pending",
        "extraction_method": "",
        "extraction_error": "",
        "page_count": meta.get("pageCount"),
        "is_duplicate_of": duplicate["id"] if duplicate else None,
        "uploaded_at": now,
        "processed_at": None,
        "created_at": now,
        "updated_at": now,
    }
    store.create_document(doc)
    store.create_audit({
        "id": new_id("aud"),
        "patient_id": patient_id,
        "actor_user_id": user["id"],
        "actor_name": user["name"],
        "actor_role": user["role"],
        "action": "document.uploaded",
        "entity_type": "medical_document",
        "entity_id": doc_id,
        "outcome": "allowed",
        "details_json": json.dumps({"originalFilename": meta["originalFilename"], "documentType": document_type, "duplicateOf": duplicate["id"] if duplicate else None}, separators=(",", ":")),
        "created_at": now,
    })
    store.conn.commit()
    saved = store.get_document(patient_id, doc_id)
    assert saved
    # process immediately (synchronous for reliability)
    processed = process_document(store, settings, user=user, patient_id=patient_id, document_id=doc_id)
    return processed


def process_document(store: Store, settings: Settings, *, user: dict[str, Any], patient_id: str, document_id: str) -> dict[str, Any]:
    access, doc = _get_patient_doc(store, user, patient_id, document_id, "twin:read")
    now = iso()
    try:
        store.update_document(document_id, {"processing_status": "processing", "updated_at": now})
        abs_path = (settings.document_storage_path / doc["storage_path"]).resolve()
        root = settings.document_storage_path.resolve()
        if root not in abs_path.parents and abs_path != root:
            raise forbidden("Invalid document storage location.")
        if not abs_path.exists():
            raise not_found("Stored document file")

        if doc["mime_type"] == "application/pdf":
            pages, method, global_error = document_extraction.extract_pdf_pages(str(abs_path), settings.max_pdf_pages)
        else:
            pages, method, global_error = document_extraction.extract_image_pages(str(abs_path))

        store.delete_document_pages(document_id)
        store.delete_document_extractions(document_id)
        page_rows = []
        for p in pages:
            row = {
                "id": new_id("dpg"),
                "document_id": document_id,
                "patient_id": patient_id,
                "page_number": p.page_number,
                "extraction_method": p.method,
                "text_content": p.text,
                "status": p.status,
                "error": p.error,
                "created_at": now,
                "updated_at": now,
            }
            store.create_document_page(row)
            page_rows.append(row)

        extraction_status = "completed"
        statuses = {p.status for p in pages}
        if statuses <= {"unavailable"}:
            extraction_status = "unavailable"
        elif "extracted" in statuses or "extracted_partial" in statuses:
            extraction_status = "completed_with_notes" if any(s in statuses for s in {"empty_or_unreadable", "error", "unavailable"}) else "completed"
        elif statuses & {"error"}:
            extraction_status = "failed"
        elif statuses & {"empty_or_unreadable"}:
            extraction_status = "empty_or_unreadable"

        items = document_extraction.build_structured_extractions(doc, page_rows)
        for item in items:
            store.create_document_extraction(item)

        store.update_document(document_id, {
            "processing_status": "processed",
            "extraction_status": extraction_status,
            "extraction_method": method,
            "extraction_error": global_error or "",
            "page_count": len(pages),
            "processed_at": now,
            "updated_at": now,
        })

        # create/update evidence source and document event for provenance/timeline integration
        twin = store.get_twin(patient_id)
        ev_title = f"Uploaded medical document · {doc['original_filename']}"
        excerpt = (page_rows[0].get("text_content") or "")[:300] if page_rows else ""
        ev = {
            "id": new_id("src"),
            "patient_id": patient_id,
            "source_type": "discharge_document" if doc["document_type"] in {"discharge_summary", "prescription"} else "clinical_note" if doc["document_type"] in {"consultation_report", "follow_up_report"} else "document_upload",
            "title": ev_title,
            "document_name": doc["original_filename"],
            "page_ref": f"{len(pages)} page(s)" if pages else "Document",
            "excerpt": excerpt or f"Uploaded {doc['document_type']} document. Extraction status: {extraction_status}.",
            "synthetic": 1 if access.patient.get("synthetic") else 0,
            "verification_status": "document_extracted",
            "extracted_by_ai": 0,
            "captured_at": doc.get("uploaded_at") or now,
            "created_at": now,
        }
        # evidence_sources.source_type is constrained in semantics but stored as TEXT; use allowed-ish value
        if ev["source_type"] == "document_upload":
            ev["source_type"] = "system_demo"
        store.create_evidence(ev)
        if twin:
            store.create_event({
                "id": new_id("evt"),
                "patient_id": patient_id,
                "twin_id": twin["id"],
                "event_type": "document_processed",
                "occurred_at": doc.get("uploaded_at") or now,
                "recorded_at": now,
                "actor_user_id": user["id"],
                "actor_name": user["name"],
                "actor_role": user["role"],
                "source_type": ev["source_type"],
                "evidence_id": ev["id"],
                "verification_status": "document_extracted",
                "title": f"Document uploaded · {doc['original_filename']}",
                "description": f"Document stored and processed (status: {extraction_status}). Extracted items are unverified until clinician review.",
                "payload_json": json.dumps({"documentId": document_id, "extractionStatus": extraction_status, "pageCount": len(pages), "extractionCount": len(items), "duplicateOf": doc.get("is_duplicate_of")}, separators=(",", ":")),
                "review_status": "pending_review" if items else "recorded",
                "created_at": now,
            })
        store.create_audit({
            "id": new_id("aud"),
            "patient_id": patient_id,
            "actor_user_id": user["id"],
            "actor_name": user["name"],
            "actor_role": user["role"],
            "action": "document.processed",
            "entity_type": "medical_document",
            "entity_id": document_id,
            "outcome": "allowed" if extraction_status not in {"failed"} else "completed_with_errors",
            "details_json": json.dumps({"extractionStatus": extraction_status, "method": method, "pageCount": len(pages), "extractionCount": len(items), "error": global_error or ""}, separators=(",", ":")),
            "created_at": now,
        })
        store.conn.commit()
    except Exception as exc:
        store.conn.rollback()
        err = str(exc)
        try:
            store.update_document(document_id, {"processing_status": "error", "extraction_status": "failed", "extraction_error": err[:1000], "updated_at": iso()})
            store.conn.commit()
        except Exception:
            store.conn.rollback()
        # do not hide failure
    return get_document_detail(store, user=user, patient_id=patient_id, document_id=document_id)


def list_documents(store: Store, *, user: dict[str, Any], patient_id: str) -> list[dict[str, Any]]:
    require_access(store, user, patient_id, "twin:read")
    return [_doc_dto(doc) for doc in store.list_documents(patient_id)]


def get_document_detail(store: Store, *, user: dict[str, Any], patient_id: str, document_id: str) -> dict[str, Any]:
    _, doc = _get_patient_doc(store, user, patient_id, document_id, "twin:read")
    pages = store.list_document_pages(document_id)
    extractions = store.list_document_extractions(document_id)
    extraction_dtos = []
    for item in extractions:
        reviews = store.list_extraction_reviews(item["id"])
        extraction_dtos.append(_extraction_dto(item, reviews))
    return {
        "document": _doc_dto(doc),
        "pages": [_page_dto(p) for p in pages],
        "extractions": extraction_dtos,
    }


def get_document_status(store: Store, *, user: dict[str, Any], patient_id: str, document_id: str) -> dict[str, Any]:
    _, doc = _get_patient_doc(store, user, patient_id, document_id, "twin:read")
    return {
        "documentId": doc["id"],
        "processingStatus": doc.get("processing_status"),
        "extractionStatus": doc.get("extraction_status"),
        "extractionMethod": doc.get("extraction_method") or "",
        "extractionError": doc.get("extraction_error") or "",
        "pageCount": doc.get("page_count"),
        "processedAt": doc.get("processed_at"),
    }


def review_extraction(store: Store, *, user: dict[str, Any], patient_id: str, document_id: str, extraction_id: str, payload: DocumentReviewRequest) -> dict[str, Any]:
    access = require_clinician(store, user, patient_id, "clinical:write")
    doc = store.get_document(patient_id, document_id)
    if not doc:
        raise not_found("Medical document")
    item = store.get_document_extraction(patient_id, extraction_id)
    if not item or item["document_id"] != document_id:
        raise not_found("Extracted item")
    now = iso()
    action = payload.action
    if action not in {"verify", "reject"}:
        raise validation_error("Action must be verify or reject.")
    prev_status = item.get("verification_status") or "unverified"
    prev_value = {
        "valueText": item.get("value_text"),
        "correctedValueText": item.get("corrected_value_text"),
        "reviewNote": item.get("review_note"),
    }
    new_status = "verified" if action == "verify" else "rejected"
    corrected = payload.corrected_value_text if (payload.corrected_value_text is not None and payload.corrected_value_text.strip() != "") else item.get("corrected_value_text")
    review_note = (payload.note or "").strip()
    updates = {
        "verification_status": new_status,
        "review_note": review_note,
        "corrected_value_text": corrected,
        "updated_at": now,
    }
    if action == "verify":
        updates.update({
            "verified_by_user_id": user["id"],
            "verified_by_name": user["name"],
            "verified_at": now,
            "rejected_by_user_id": None,
            "rejected_by_name": None,
            "rejected_at": None,
        })
    else:
        updates.update({
            "rejected_by_user_id": user["id"],
            "rejected_by_name": user["name"],
            "rejected_at": now,
        })
    store.update_document_extraction(extraction_id, updates)
    store.create_extraction_review({
        "id": new_id("dxr"),
        "extraction_id": extraction_id,
        "document_id": document_id,
        "patient_id": patient_id,
        "action": action,
        "actor_user_id": user["id"],
        "actor_name": user["name"],
        "actor_role": user["role"],
        "previous_verification_status": prev_status,
        "new_verification_status": new_status,
        "previous_value_json": json.dumps(prev_value, separators=(",", ":")),
        "new_value_json": json.dumps({"verificationStatus": new_status, "correctedValueText": corrected, "note": review_note}, separators=(",", ":")),
        "note": review_note,
        "created_at": now,
    })

    # ensure evidence and twin integration for verified items only
    twin = store.get_twin(patient_id)
    evidence_id = item.get("evidence_id")
    if twin and not evidence_id:
        ev = {
            "id": new_id("src"),
            "patient_id": patient_id,
            "source_type": "discharge_document" if doc["document_type"] in {"discharge_summary", "prescription"} else "clinician_note",
            "title": f"Extracted item · {item['label']}",
            "document_name": doc["original_filename"],
            "page_ref": f"Page {item.get('page_number')}" if item.get("page_number") else "Document",
            "excerpt": (item.get("source_text") or item.get("value_text") or "")[:500],
            "synthetic": 1 if access.patient.get("synthetic") else 0,
            "verification_status": "clinician_verified" if new_status == "verified" else "awaiting_review",
            "extracted_by_ai": 0,
            "captured_at": doc.get("uploaded_at") or now,
            "created_at": now,
        }
        store.create_evidence(ev)
        evidence_id = ev["id"]
        store.update_document_extraction(extraction_id, {"evidence_id": evidence_id})
    elif evidence_id:
        store.update_evidence_verification(evidence_id, "clinician_verified" if new_status == "verified" else "awaiting_review")

    if twin and new_status == "verified":
        # record a verified-extraction event and bump twin (only for clinician-verified info)
        event_id = new_id("evt")
        store.create_event({
            "id": event_id,
            "patient_id": patient_id,
            "twin_id": twin["id"],
            "event_type": "document_processed",
            "occurred_at": now,
            "recorded_at": now,
            "actor_user_id": user["id"],
            "actor_name": user["name"],
            "actor_role": user["role"],
            "source_type": "clinician_note",
            "evidence_id": evidence_id,
            "verification_status": "clinician_verified",
            "title": f"Extraction verified · {item['label']}",
            "description": f"Clinician verified extracted {item['item_type']} from {doc['original_filename']} (page {item.get('page_number') or '?'}).",
            "payload_json": json.dumps({"documentId": document_id, "extractionId": extraction_id, "itemType": item["item_type"], "corrected": bool(corrected)}, separators=(",", ":")),
            "review_status": "reviewed",
            "created_at": now,
        })
        version = _bump_twin(store, patient=access.patient, now=now, reason="Verified document extraction integrated")
    else:
        version = store.get_twin(patient_id)["version"] if store.get_twin(patient_id) else 1

    store.create_audit({
        "id": new_id("aud"),
        "patient_id": patient_id,
        "actor_user_id": user["id"],
        "actor_name": user["name"],
        "actor_role": user["role"],
        "action": f"document_extraction.{action}d",
        "entity_type": "document_extraction",
        "entity_id": extraction_id,
        "outcome": "allowed",
        "details_json": json.dumps({"documentId": document_id, "previousStatus": prev_status, "newStatus": new_status}, separators=(",", ":")),
        "created_at": now,
    })
    store.conn.commit()
    updated = store.get_document_extraction(patient_id, extraction_id)
    assert updated
    return {"extraction": _extraction_dto(updated, store.list_extraction_reviews(extraction_id)), "twinVersion": version}


def _bump_twin(store: Store, *, patient: dict[str, Any], now: str, reason: str) -> int:
    twin = store.get_twin(patient["id"])
    assert twin is not None
    milestones = store.list_milestones(patient["id"])
    alerts = store.list_alerts(patient["id"])
    status, status_reason = twin_service.compute_status(alerts, milestones)
    version = int(twin["version"]) + 1
    store.update_twin(twin["id"], version=version, status=status, reason=status_reason, updated_at=now)
    twin["version"] = version
    twin["status"] = status
    twin["updated_at"] = now
    snapshot = twin_service.snapshot_payload(store, patient=patient, twin=twin)
    store.create_snapshot({
        "id": new_id("snp"),
        "patient_id": patient["id"],
        "twin_id": twin["id"],
        "version": version,
        "reason": reason,
        "snapshot_json": json.dumps(snapshot, separators=(",", ":")),
        "created_at": now,
    })
    return version


def _grounded_evidence(store: Store, patient_id: str) -> dict[str, Any]:
    docs = store.list_documents(patient_id)
    extractions = []
    for doc in docs:
        for ex in store.list_document_extractions(doc["id"]):
            extractions.append(ex)
    verified = [e for e in extractions if e.get("verification_status") == "verified"]
    unverified = [e for e in extractions if e.get("verification_status") != "verified"]
    meds = store.list_medications(patient_id)
    followups = store.list_follow_ups(patient_id)
    checkins = store.list_checkins(patient_id, limit=5)
    observations = store.list_observations(patient_id)
    labs = store.list_lab_results(patient_id)
    encounters = store.list_encounters(patient_id)
    evidence = store.list_evidence(patient_id)
    return {
        "documents": docs,
        "verifiedExtractions": verified,
        "unverifiedExtractions": unverified,
        "medications": meds,
        "followUps": followups,
        "checkIns": checkins,
        "observations": observations,
        "labs": labs,
        "encounters": encounters,
        "evidenceSources": evidence,
    }


def generate_guidance(store: Store, settings: Settings, ai_service, *, user: dict[str, Any], patient_id: str, payload: GuidanceRequest) -> dict[str, Any]:
    require_access(store, user, patient_id, "summary:read" if user["role"] != "clinician" else "twin:read")
    ctx = _grounded_evidence(store, patient_id)
    now = iso()
    gtype = payload.guidance_type
    question = (payload.question or "").strip()

    def cite_doc_items(items, limit=10):
        c = []
        for it in items[:limit]:
            doc = store.get_document(patient_id, it["document_id"]) if it.get("document_id") else None
            c.append({
                "type": "extraction",
                "id": it["id"],
                "documentId": it.get("document_id"),
                "documentName": doc["original_filename"] if doc else None,
                "pageNumber": it.get("page_number"),
                "label": it.get("label"),
                "verificationStatus": it.get("verification_status"),
            })
        return c

    verified = ctx["verifiedExtractions"]
    unverified = ctx["unverifiedExtractions"]
    citations = cite_doc_items(verified, 12)
    sections = []
    # deterministic, evidence-grounded summaries always available
    sections.append(f"Source-grounded summary for patient {patient_id}. Unverified extracted information is listed separately and must not be treated as fact.")
    if gtype == "document_explanation":
        sections.append(f"Uploaded documents: {len(ctx['documents'])}. Verified extracted items: {len(verified)}. Unverified extracted items: {len(unverified)}.")
        for it in verified[:8]:
            sections.append(f"- [Verified, p.{it.get('page_number') or '?'}] {it['label']}: {it.get('corrected_value_text') or it.get('value_text') or '(no value text)'} (source: { (it.get('source_text') or '')[:120] })")
        if unverified:
            sections.append("Unverified items (require clinician review): " + "; ".join([f"{u['label']} (p.{u.get('page_number') or '?'})" for u in unverified[:8]]))
        if not ctx['documents']:
            sections.append("No supporting uploaded documents were found for this patient.")
    elif gtype == "medical_history_summary":
        sections.append(f"Clinical encounters: {len(ctx['encounters'])}. Lab results: {len(ctx['labs'])}. Medications on record: {len(ctx['medications'])}. Follow-ups: {len(ctx['followUps'])}. Recent check-ins: {len(ctx['checkIns'])}.")
        for enc in ctx['encounters'][:5]:
            sections.append(f"- Encounter {enc.get('occurred_at')}: {enc.get('encounter_type')} — {enc.get('summary','')[:140]} (verification: {enc.get('verification_status')})")
        for lab in ctx['labs'][:5]:
            sections.append(f"- Lab {lab.get('collected_at')}: {lab.get('test_name')} = {lab.get('value_numeric') if lab.get('value_numeric') is not None else lab.get('value_text')} {lab.get('unit') or ''} (verification: {lab.get('verification_status')})")
    elif gtype == "lab_findings":
        if not ctx['labs'] and not [e for e in verified if e['item_type']=='lab_finding']:
            sections.append("No documented laboratory findings were found.")
        for lab in ctx['labs'][:10]:
            parts = [f"{lab.get('test_name')}: {lab.get('value_numeric') if lab.get('value_numeric') is not None else lab.get('value_text')} {lab.get('unit') or ''}".strip()]
            if lab.get('source_range_text'):
                parts.append(f"source range (as provided): {lab['source_range_text']}")
            if lab.get('comparison_note'):
                parts.append(lab['comparison_note'])
            sections.append("- " + " | ".join(parts) + f" (verification: {lab.get('verification_status')})")
        for it in [e for e in verified if e['item_type']=='lab_finding'][:10]:
            sections.append(f"- [Verified extraction p.{it.get('page_number')}] {it['label']}: {it.get('corrected_value_text') or it.get('value_text')} {it.get('unit') or ''} {('range: '+it['reference_range']) if it.get('reference_range') else ''}")
    elif gtype == "discharge_instructions":
        found = False
        for enc in ctx['encounters']:
            if (enc.get('discharge_instructions') or '').strip():
                sections.append(f"- Discharge instructions ({enc.get('occurred_at')}, {enc.get('verification_status')}): {enc['discharge_instructions']}")
                found = True
        for it in [e for e in verified if e['item_type']=='discharge_instruction'][:10]:
            sections.append(f"- [Verified extraction p.{it.get('page_number')}] {it.get('corrected_value_text') or it.get('value_text')}")
            found = True
        if not found:
            sections.append("No supporting clinician-documented discharge instructions were found.")
    elif gtype == "medication_instructions":
        if not ctx['medications']:
            sections.append("No documented medication instructions were found.")
        for med in ctx['medications']:
            sections.append(f"- {med.get('name')} {med.get('dosage')} {med.get('route')} {med.get('frequency')} ({med.get('duration')}). Instructions as documented: {med.get('instructions')} (verification: {med.get('verification_status')})")
        for it in [e for e in verified if e['item_type']=='medication_mention'][:8]:
            sections.append(f"- [Verified extraction p.{it.get('page_number')}] {it.get('corrected_value_text') or it.get('value_text')}")
        sections.append("Medication doses/instructions are shown only as documented; this guidance does not modify doses.")
    elif gtype == "precautions":
        found = False
        for it in [e for e in verified if e['item_type']=='precaution'][:12]:
            sections.append(f"- [Verified, p.{it.get('page_number')}] {it.get('corrected_value_text') or it.get('value_text')}")
            found = True
        for enc in ctx['encounters']:
            txt = (enc.get('discharge_instructions') or '') + ' ' + (enc.get('follow_up_plan') or '')
            if 'warning' in txt.lower() or 'emergency' in txt.lower() or 'seek' in txt.lower():
                sections.append(f"- Documented guidance ({enc.get('occurred_at')}): {txt[:220]}")
                found = True
        if not found:
            sections.append("No supporting clinician-documented precautions were found.")
    elif gtype == "follow_up":
        if not ctx['followUps'] and not [e for e in verified if e['item_type']=='follow_up']:
            sections.append("No documented follow-up requirements were found.")
        for fu in ctx['followUps'][:10]:
            sections.append(f"- {fu.get('scheduled_for')}: {fu.get('title')} with {fu.get('clinician_name')} ({fu.get('specialty')}) at {fu.get('location')} — {fu.get('notes')} (verification: {fu.get('verification_status')})")
        for it in [e for e in verified if e['item_type']=='follow_up'][:8]:
            sections.append(f"- [Verified extraction p.{it.get('page_number')}] {it.get('corrected_value_text') or it.get('value_text')}")
    elif gtype == "clinician_questions":
        sections.append("Questions to prepare for your clinician (based on available documented information):")
        sections.append("- Which documented findings above need follow-up, and what changes should prompt urgent contact?")
        if ctx['labs']:
            sections.append("- Can you explain how my recent documented lab results relate to my recovery plan?")
        if ctx['medications']:
            sections.append("- Are my documented medication instructions still current, and what side effects should I watch for?")
        if not verified and not ctx['labs'] and not ctx['medications']:
            sections.append("No supporting clinician-documented records were found to tailor specific questions; bring available documents to your visit.")
    elif gtype == "historical_comparison":
        comparable = []
        for it in [e for e in verified if e['item_type']=='lab_finding' and e.get('unit')]:
            comparable.append(it)
        if len(comparable) < 2:
            sections.append("No comparable historical results with sufficient context (verified values, same units/dates/context) were found.")
        else:
            sections.append("Available verified extracted findings (compare only when units/dates/context match):")
            for it in comparable[:12]:
                sections.append(f"- {it['label']}: {it.get('corrected_value_text') or it.get('value_text')} {it.get('unit') or ''} (p.{it.get('page_number')}, doc {it.get('document_id')})")
    else:
        sections.append("Grounded guidance based on available patient records and verified document extractions.")
        sections.append(f"Documents: {len(ctx['documents'])}, verified extractions: {len(verified)}, unverified: {len(unverified)}.")
        if question:
            sections.append(f"Question noted: {question}")

    if unverified:
        sections.append(f"Note: {len(unverified)} extracted item(s) remain unverified and were not treated as confirmed clinical facts.")

    deterministic_answer = "\n".join(sections)
    ai_status = ai_service.status() if ai_service else {"state": "unavailable", "configured": False, "model": ""}
    final_answer = deterministic_answer
    mode = "deterministic_grounded"
    grounded = True
    ai_state = ai_status.get("state", "not_configured")

    # Optional Gemini enhancement: only if configured and question/context merits; but must remain grounded and safe
    if ai_service and ai_status.get("configured") and question:
        try:
            # reuse explain boundary with grounded context by asking a constrained question
            # include explicit evidence and instruct not to diagnose/prescribe/invent
            grounded_question = (
                f"Using only the following evidence-grounded summary, provide a patient-friendly explanation. "
                f"Do not diagnose, prescribe, change doses, invent thresholds, or present unverified information as fact. "
                f"Question: {question}\n\nEVIDENCE SUMMARY:\n{deterministic_answer[:6000]}"
            )
            ai_result = ai_service.explain(store, user=user, patient_id=patient_id, question=grounded_question)
            final_answer = deterministic_answer + "\n\nAI explanation (grounded in available evidence, separate from clinician-verified instructions):\n" + ai_result.get("answer", "")
            mode = "grounded_with_ai_explanation"
            ai_state = "used"
            citations = citations + [{"type": "ai_citation", "id": c} for c in (ai_result.get("citations") or [])]
        except Exception as exc:
            final_answer = deterministic_answer + f"\n\nAI explanation unavailable: {getattr(exc, 'message', str(exc))}"
            ai_state = ai_status.get("state", "error")

    record = {
        "id": new_id("gdh"),
        "patient_id": patient_id,
        "requested_by_user_id": user.get("id"),
        "requested_by_name": user.get("name", ""),
        "requested_by_role": user.get("role", ""),
        "question": question,
        "guidance_type": gtype,
        "mode": mode,
        "ai_state": ai_state,
        "model": ai_status.get("model", "") if mode == "grounded_with_ai_explanation" else "",
        "answer": final_answer,
        "citations_json": json.dumps(citations, separators=(",", ":")),
        "evidence_json": json.dumps({"documentCount": len(ctx['documents']), "verifiedExtractionCount": len(verified), "unverifiedExtractionCount": len(unverified)}, separators=(",", ":")),
        "grounded": 1 if grounded else 0,
        "created_at": now,
    }
    store.create_guidance_history(record)
    store.create_audit({
        "id": new_id("aud"),
        "patient_id": patient_id,
        "actor_user_id": user.get("id"),
        "actor_name": user.get("name", ""),
        "actor_role": user.get("role", ""),
        "action": "guidance.generated",
        "entity_type": "guidance_history",
        "entity_id": record["id"],
        "outcome": "allowed",
        "details_json": json.dumps({"guidanceType": gtype, "mode": mode, "aiState": ai_state}, separators=(",", ":")),
        "created_at": now,
    })
    store.conn.commit()
    return {
        "id": record["id"],
        "patientId": patient_id,
        "guidanceType": gtype,
        "mode": mode,
        "aiState": ai_state,
        "model": record["model"],
        "grounded": True,
        "answer": final_answer,
        "citations": citations,
        "evidenceSummary": json.loads(record["evidence_json"]),
        "unverifiedItemsExcludedFromConfirmation": len(unverified),
        "createdAt": now,
    }


def list_guidance_history(store: Store, *, user: dict[str, Any], patient_id: str) -> list[dict[str, Any]]:
    require_access(store, user, patient_id, "summary:read" if user["role"] != "clinician" else "twin:read")
    rows = store.list_guidance_history(patient_id, limit=50)
    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "patientId": r["patient_id"],
            "guidanceType": r["guidance_type"],
            "mode": r["mode"],
            "aiState": r["ai_state"],
            "model": r.get("model") or "",
            "question": r.get("question") or "",
            "answer": r.get("answer") or "",
            "citations": r.get("citations") or [],
            "evidence": r.get("evidence") or [],
            "grounded": bool(r.get("grounded")),
            "requestedBy": {"name": r.get("requested_by_name"), "role": r.get("requested_by_role")},
            "createdAt": r["created_at"],
        })
    return result


# ------------------------------------------------------- document intelligence
def _analysis_payload(store: Store, *, user: dict[str, Any], patient_id: str, document_id: str, ai_status: dict[str, Any] | None = None) -> dict[str, Any]:
    _, doc = _get_patient_doc(store, user, patient_id, document_id, "twin:read")
    pages = store.list_document_pages(document_id)
    extractions = store.list_document_extractions(document_id)
    return document_analysis.analyze_document(
        document=doc, pages=pages, extractions=extractions, ai_status=ai_status
    )


def get_document_analysis(store: Store, *, user: dict[str, Any], patient_id: str, document_id: str, ai_status: dict[str, Any] | None = None) -> dict[str, Any]:
    return _analysis_payload(store, user=user, patient_id=patient_id, document_id=document_id, ai_status=ai_status)


def get_document_explanation(
    store: Store, *, user: dict[str, Any], patient_id: str, document_id: str, mode: str = "report"
) -> dict[str, Any]:
    """Return the cached grounded AI explanation, or an honest unavailable state."""
    _, doc = _get_patient_doc(store, user, patient_id, document_id, "twin:read")
    mode = "prescription" if mode == "prescription" else "report"
    cached = store.latest_ai_explanation(document_id, mode)
    if cached:
        return cached
    return {
        "available": False,
        "documentId": document_id,
        "documentName": doc["original_filename"],
        "mode": mode,
        "analysisMode": "deterministic_extraction_analysis",
        "aiUsed": False,
        "reason": "No grounded AI explanation has been generated for this document yet.",
        "generatedAt": iso(),
    }


def explain_document(
    store: Store,
    ai: Any,
    *,
    user: dict[str, Any],
    patient_id: str,
    document_id: str,
    mode: str = "report",
    force: bool = False,
) -> dict[str, Any]:
    return ai.explain_document(
        store,
        user=user,
        patient_id=patient_id,
        document_id=document_id,
        mode=mode,
        force=force,
    )


def get_document_prescription(store: Store, *, user: dict[str, Any], patient_id: str, document_id: str) -> dict[str, Any]:
    _, doc = _get_patient_doc(store, user, patient_id, document_id, "twin:read")
    pages = store.list_document_pages(document_id)
    parsed = document_analysis.parse_prescription(pages)
    parsed["documentId"] = document_id
    parsed["documentName"] = doc["original_filename"]
    parsed["documentType"] = doc["document_type"]
    parsed["generatedAt"] = iso()
    return parsed


def get_document_file(store: Store, settings: Settings, *, user: dict[str, Any], patient_id: str, document_id: str) -> tuple[Path, str, str]:
    _, doc = _get_patient_doc(store, user, patient_id, document_id, "twin:read")
    abs_path = (settings.document_storage_path / doc["storage_path"]).resolve()
    root = settings.document_storage_path.resolve()
    if root not in abs_path.parents and abs_path != root:
        raise forbidden("Invalid document storage location.")
    if not abs_path.exists():
        raise not_found("Stored document file")
    store.create_audit({
        "id": new_id("aud"),
        "patient_id": patient_id,
        "actor_user_id": user["id"],
        "actor_name": user["name"],
        "actor_role": user["role"],
        "action": "document.viewed",
        "entity_type": "medical_document",
        "entity_id": document_id,
        "outcome": "allowed",
        "details_json": json.dumps({"originalFilename": doc["original_filename"]}, separators=(",", ":")),
        "created_at": iso(),
    })
    store.conn.commit()
    return abs_path, doc.get("mime_type") or "application/octet-stream", doc["original_filename"]


def reprocess_document(store: Store, settings: Settings, *, user: dict[str, Any], patient_id: str, document_id: str) -> dict[str, Any]:
    if user["role"] not in {"patient", "clinician"}:
        raise forbidden("Only the patient or a clinician can reprocess a document.")
    _get_patient_doc(store, user, patient_id, document_id, "twin:read")
    now = iso()
    store.create_audit({
        "id": new_id("aud"),
        "patient_id": patient_id,
        "actor_user_id": user["id"],
        "actor_name": user["name"],
        "actor_role": user["role"],
        "action": "document.reprocess_requested",
        "entity_type": "medical_document",
        "entity_id": document_id,
        "outcome": "allowed",
        "details_json": json.dumps({"requestedAt": now}, separators=(",", ":")),
        "created_at": now,
    })
    store.update_document(document_id, {"processing_status": "queued", "extraction_error": "", "updated_at": now})
    store.conn.commit()
    return process_document(store, settings, user=user, patient_id=patient_id, document_id=document_id)


def compare_patient_reports(store: Store, *, user: dict[str, Any], patient_id: str) -> dict[str, Any]:
    require_access(store, user, patient_id, "twin:read")
    documents = store.list_documents(patient_id)
    extractions_by_document = {doc["id"]: store.list_document_extractions(doc["id"]) for doc in documents}
    pages_by_document = {doc["id"]: store.list_document_pages(doc["id"]) for doc in documents}
    report = document_analysis.compare_reports(
        documents=documents,
        extractions_by_document=extractions_by_document,
        pages_by_document=pages_by_document,
    )
    report["patientId"] = patient_id
    return report
