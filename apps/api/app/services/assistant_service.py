from __future__ import annotations

import json
import re
from typing import Any

from app.ai.service import AiService
from app.errors import ApiError
from app.repositories.store import Store
from app.safety.prompt_guard import scan_for_injection
from app.services import document_analysis
from app.services.auth import require_access
from app.utils import iso, new_id

MAX_QUESTION = 500


def _fmt_number(value: float) -> str:
    return f"{value:g}"


def _answer_route(question: str) -> str:
    text = question.lower()
    if re.search(r"\bcompare\b|difference|changed|previous|trend", text):
        return "comparison"
    if re.search(r"prescription|medicine|medication|tablet|dose|dosage", text):
        return "prescription"
    if re.search(r"precaution|warning|watch for|red flag|emergency", text):
        return "precautions"
    if re.search(r"follow[- ]?up|next appointment|next visit", text):
        return "follow_up"
    if re.search(r"medical history|history|summar", text):
        return "history"
    if re.search(r"question.*(doctor|clinician|consult)|ask my (doctor|clinician)", text):
        return "questions"
    if re.search(
        r"blood|lab|report|result|value|hemoglobin|glucose|creatinine|thyroid|cholesterol|"
        r"hba1c|a1c|tsh|ldl|hdl|triglyceride|ferritin|platelet",
        text,
    ):
        return "lab"
    return "general"


def _collect(store: Store, patient_id: str) -> dict[str, Any]:
    documents = store.list_documents(patient_id)
    extractions: dict[str, list[dict[str, Any]]] = {}
    pages: dict[str, list[dict[str, Any]]] = {}
    for doc in documents:
        extractions[doc["id"]] = store.list_document_extractions(doc["id"])
        pages[doc["id"]] = store.list_document_pages(doc["id"])
    return {
        "documents": documents,
        "extractions": extractions,
        "pages": pages,
        "labs": store.list_lab_results(patient_id),
        "medications": store.list_medications(patient_id),
        "followUps": store.list_follow_ups(patient_id),
        "encounters": store.list_encounters(patient_id),
        "evidence": store.list_evidence(patient_id),
        "observations": store.list_observations(patient_id),
        "checkins": store.list_checkins(patient_id, limit=3),
    }


def _lab_facts(store: Store, patient_id: str, data: dict[str, Any], question: str) -> tuple[list[str], list[dict[str, Any]], str]:
    canonical = document_analysis.canonical_analyte(question)
    documents = data["documents"]
    selected = []
    for doc in documents:
        for item in data["extractions"][doc["id"]]:
            if item.get("item_type") != "lab_finding":
                continue
            item_canonical = document_analysis.canonical_analyte(item.get("label") or "")
            if canonical and item_canonical != canonical:
                continue
            selected.append((doc, item))

    if not selected:
        if canonical:
            label = document_analysis.analyte_display_name(canonical)
            return (
                [f"No uploaded document records a value for {label}."],
                [],
                f"No {label} reading exists in the uploaded documents for this patient, so there is nothing to explain from their own records.",
            )
        # A generic lab question with no extracted lab values must degrade to a clear
        # message, never to an empty selection that raises.
        return (
            ["No readable lab values were extracted from the uploaded documents."],
            [],
            "No lab value could be read from this patient's uploaded documents, so there is "
            "nothing to explain from their own records yet.",
        )

    # Prefer readings from the most recently uploaded blood/lab report.
    docs_sorted = sorted(documents, key=lambda d: d.get("uploaded_at") or "", reverse=True)
    order = {doc["id"]: index for index, doc in enumerate(docs_sorted)}
    selected.sort(key=lambda pair: order.get(pair[0]["id"], 10**6))
    latest_doc = selected[0][0]
    latest_items = [(doc, item) for doc, item in selected if doc["id"] == latest_doc["id"]]

    facts: list[str] = []
    citations: list[dict[str, Any]] = []
    for doc, item in latest_items[:12]:
        value = (item.get("corrected_value_text") or item.get("value_text") or "").strip()
        unit = item.get("unit") or ""
        rng = item.get("reference_range") or ""
        line = f"{item['label']}: {value}{(' ' + unit) if unit and unit not in value else ''}"
        if rng:
            line += f" (reference range printed on the report: {rng})"
        line += f" — {item.get('verification_status') or 'unverified'}, page {item.get('page_number') or '?'}"
        facts.append(line)
        citations.append(
            {
                "type": "extraction",
                "id": item["id"],
                "documentId": doc["id"],
                "documentName": doc.get("original_filename"),
                "pageNumber": item.get("page_number"),
                "label": item.get("label"),
                "verificationStatus": item.get("verification_status") or "unverified",
                "quote": (item.get("source_text") or "")[:280],
            }
        )

    explanation_parts = [
        f"These are the values extracted from {latest_doc.get('original_filename')} "
        f"(uploaded {str(latest_doc.get('uploaded_at'))[:10]})."
    ]
    if canonical:
        gloss = document_analysis.analyte_explanation(canonical)
        if gloss:
            explanation_parts.append(gloss)
    explanation_parts.append(
        "A report value only means what the reporting laboratory's own reference range says in that context. "
        "CareTwin AI does not judge whether a value is normal, and extracted values stay unverified until a clinician reviews them."
    )
    uncertain = (
        "No clinician has verified the extracted values quoted above."
        if any(item.get("verification_status") != "verified" for _, item in latest_items)
        else "The values quoted above are clinician verified in this record."
    )
    return facts, citations, " ".join(explanation_parts) + " " + uncertain


def _comparison_facts(patient_id: str, data: dict[str, Any], question: str) -> tuple[list[str], list[dict[str, Any]], str]:
    report = document_analysis.compare_reports(
        documents=data["documents"],
        extractions_by_document=data["extractions"],
        pages_by_document=data["pages"],
    )
    canonical = document_analysis.canonical_analyte(question)
    rows = report["comparisons"]
    if canonical:
        rows = [row for row in rows if row["canonicalTest"] == canonical]
    # Comparable pairs first: a same-day or identical pair is not a change story.
    rows = sorted(rows, key=lambda row: (not row["comparable"], row["label"]))
    if not rows:
        if canonical:
            label = document_analysis.analyte_display_name(canonical)
            return (
                [f"Only one compatible {label} reading exists, or the units do not match across reports."],
                [],
                "A comparison needs the same test with the same unit in two different documents. "
                "No such pair exists for this test in the uploaded records, so no change is reported.",
            )
        return (
            ["No compatible pair of readings was found across the uploaded documents."],
            [],
            "Comparisons are only offered for the same test with the same unit in two different documents.",
        )

    facts: list[str] = []
    citations: list[dict[str, Any]] = []
    for row in rows[:6]:
        prev, latest = row["previous"], row["latest"]
        facts.append(
            f"{row['label']}: {_fmt_number(prev['value'])} {row['unit']} on {prev['date']} → "
            f"{_fmt_number(latest['value'])} {row['unit']} on {latest['date']} "
            f"(difference {row['difference']:+g} {row['unit']}; {row['direction']})"
        )
        for side in (prev, latest):
            citations.append(
                {
                    "type": "extraction",
                    "id": side["extractionId"],
                    "documentId": side["documentId"],
                    "documentName": side["documentName"],
                    "pageNumber": side["pageNumber"],
                    "label": side["label"],
                    "verificationStatus": side["verificationStatus"],
                    "quote": f"{side['valueText']} · {side['date']}",
                }
            )
    unverified = [row for row in rows if not row["verification"]["bothVerified"]]
    explanation = (
        "The change shown is arithmetic between the two reported values with the same unit. "
        "It is not an interpretation of whether that change matters, and it is not a diagnosis."
    )
    if unverified:
        explanation += f" {len(unverified)} comparison(s) include unverified extracted values."
    return facts, citations, explanation


def _prescription_facts(data: dict[str, Any], question: str) -> tuple[list[str], list[dict[str, Any]], str]:
    prescription_docs = [
        doc for doc in data["documents"]
        if doc.get("document_type") == "prescription"
        or any(item.get("item_type") == "medication_mention" for item in data["extractions"][doc["id"]])
    ]
    if not prescription_docs:
        return (
            ["No uploaded document contains a prescription."],
            [],
            "There is no prescription text in this patient's uploaded records, so no medicine instruction can be explained from evidence.",
        )
    prescription_docs.sort(key=lambda d: d.get("uploaded_at") or "", reverse=True)
    doc = prescription_docs[0]
    parsed = document_analysis.parse_prescription(data["pages"][doc["id"]])
    facts: list[str] = []
    citations: list[dict[str, Any]] = []
    for med in parsed["medicines"][:10]:
        facts.append(
            f"{med['name']}: dose {med['dosage'] or 'not readable'}, frequency {med['frequency'] or 'not readable'}, "
            f"timing {med['timing'] or 'not stated'}, duration {med['duration'] or 'not stated'} "
            f"(page {med['pageNumber']})"
        )
        citations.append(
            {
                "type": "prescription_line",
                "id": f"{doc['id']}:{med['pageNumber']}",
                "documentId": doc["id"],
                "documentName": doc.get("original_filename"),
                "pageNumber": med["pageNumber"],
                "label": med["name"],
                "verificationStatus": "unverified",
                "quote": med["sourceText"][:280],
            }
        )
    if not facts:
        facts.append("The prescription document has no reliably readable medicine line.")
    explanation = (
        "These fields restate the written prescription from "
        f"{doc.get('original_filename')} and are unverified. CareTwin AI does not prescribe, change a dose, "
        "or advise stopping any medicine. Confirm every instruction with the prescriber or pharmacist."
    )
    if parsed["clarifications"]:
        explanation += " Clarification needed: " + "; ".join(parsed["clarifications"][:3])
    return facts, citations, explanation


def _precaution_facts(data: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]], str]:
    facts: list[str] = []
    citations: list[dict[str, Any]] = []
    for doc in data["documents"]:
        for item in data["extractions"][doc["id"]]:
            if item.get("item_type") != "precaution" or item.get("verification_status") != "verified":
                continue
            facts.append(f"{item.get('corrected_value_text') or item.get('value_text')} (page {item.get('page_number')})")
            citations.append(
                {
                    "type": "extraction",
                    "id": item["id"],
                    "documentId": doc["id"],
                    "documentName": doc.get("original_filename"),
                    "pageNumber": item.get("page_number"),
                    "label": item.get("label"),
                    "verificationStatus": "verified",
                    "quote": (item.get("source_text") or "")[:280],
                }
            )
    for enc in data["encounters"]:
        text = (enc.get("discharge_instructions") or "") + " " + (enc.get("follow_up_plan") or "")
        if not text.strip():
            continue
        if re.search(r"warning|emergency|seek|avoid|precaution", text, re.IGNORECASE):
            facts.append(f"{text.strip()[:260]} ({enc.get('occurred_at')}, {enc.get('verification_status')})")
    if not facts:
        return (
            ["No clinician-verified precaution text exists in the uploaded records."],
            [],
            "Only clinician-verified document text is quoted for precautions. Nothing verified was found, so no advice is given.",
        )
    return facts, citations, "Quoted only from verified document text or recorded encounters; nothing was added."


def _follow_up_facts(data: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]], str]:
    facts: list[str] = []
    citations: list[dict[str, Any]] = []
    for item in data["followUps"]:
        facts.append(
            f"{item.get('scheduled_for')}: {item.get('title')} with {item.get('clinician_name')} "
            f"({item.get('verification_status')})"
        )
    for doc in data["documents"]:
        for item in data["extractions"][doc["id"]]:
            if item.get("item_type") != "follow_up":
                continue
            facts.append(
                f"{item.get('corrected_value_text') or item.get('value_text')} "
                f"(page {item.get('page_number')}, {item.get('verification_status')})"
            )
            citations.append(
                {
                    "type": "extraction",
                    "id": item["id"],
                    "documentId": doc["id"],
                    "documentName": doc.get("original_filename"),
                    "pageNumber": item.get("page_number"),
                    "label": item.get("label"),
                    "verificationStatus": item.get("verification_status") or "unverified",
                    "quote": (item.get("source_text") or "")[:280],
                }
            )
    if not facts:
        return (
            ["No follow-up instruction exists in the uploaded records."],
            [],
            "No follow-up requirement was found in the structured records or uploaded documents.",
        )
    return facts, citations, "These entries are quoted from the structured record or the document text exactly as written."


def _history_facts(data: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]], str]:
    facts = [
        f"{len(data['documents'])} uploaded document(s), {sum(len(v) for v in data['extractions'].values())} extracted item(s).",
        f"{len(data['encounters'])} recorded encounter(s), {len(data['labs'])} structured lab result(s), "
        f"{len(data['medications'])} documented medication(s), {len(data['followUps'])} follow-up(s).",
    ]
    for enc in data["encounters"][:4]:
        facts.append(f"Encounter {enc.get('occurred_at')}: {enc.get('encounter_type')} — {(enc.get('summary') or '')[:160]}")
    return facts, [], (
        "This is a count-and-quote summary of stored records. It does not infer a condition or a "
        "clinical conclusion from the presence of documents."
    )


def _questions_facts(data: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]], str]:
    facts: list[str] = []
    citations: list[dict[str, Any]] = []
    for doc in data["documents"][:10]:
        analysis = document_analysis.analyze_document(
            document=doc,
            pages=data["pages"][doc["id"]],
            extractions=data["extractions"][doc["id"]],
        )
        for question in analysis["questionsToAsk"][:3]:
            facts.append(f"{question['question']} (basis: {question['basis']})")
    facts.append("What should prompt urgent contact, and which findings need follow-up?")
    if not citations:
        citations = []
    return facts[:10], citations, (
        "Questions are generated from gaps and unverified values in your own documents. They are prompts for a "
        "consultation, not clinical advice."
    )


def _general_facts(data: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]], str]:
    verified = sum(
        1
        for doc_id in data["extractions"]
        for item in data["extractions"][doc_id]
        if item.get("verification_status") == "verified"
    )
    total = sum(len(v) for v in data["extractions"].values())
    facts = [
        f"Uploaded documents: {len(data['documents'])}.",
        f"Extracted items: {total} ({verified} clinician verified, {total - verified} awaiting review).",
        f"Recorded encounters: {len(data['encounters'])}; documented medications: {len(data['medications'])}; "
        f"follow-ups: {len(data['followUps'])}.",
    ]
    return facts, [], (
        "I can only answer from this patient's stored records. Ask about a specific report, medicine, "
        "precaution, follow-up or comparison to get page-level references."
    )


def ask_assistant(
    store: Store,
    ai: AiService,
    *,
    user: dict[str, Any],
    patient_id: str,
    question: str,
    conversation_id: str | None = None,
    document_id: str | None = None,
) -> dict[str, Any]:
    access = require_access(store, user, patient_id, "summary:read")
    if user["role"] == "caregiver":
        raise ValueError("caregiver_not_permitted")

    data = _collect(store, patient_id)
    if document_id:
        if not any(doc["id"] == document_id for doc in data["documents"]):
            from app.errors import not_found

            raise not_found("Medical document")
        data["documents"] = [doc for doc in data["documents"] if doc["id"] == document_id]

    route = _answer_route(question)
    injection = scan_for_injection(question)
    canonical_hint = document_analysis.canonical_analyte(question)
    if route == "comparison":
        facts, citations, explanation = _comparison_facts(patient_id, data, question)
    elif route == "prescription":
        facts, citations, explanation = _prescription_facts(data, question)
    elif route == "precautions":
        facts, citations, explanation = _precaution_facts(data)
    elif route == "follow_up":
        facts, citations, explanation = _follow_up_facts(data)
    elif route == "questions":
        facts, citations, explanation = _questions_facts(data)
    elif route == "history":
        facts, citations, explanation = _history_facts(data)
    elif route == "lab":
        facts, citations, explanation = _lab_facts(store, patient_id, data, question)
    elif canonical_hint:
        facts, citations, explanation = _lab_facts(store, patient_id, data, question)
    else:
        facts, citations, explanation = _general_facts(data)

    ai_status = ai.status()
    mode = "deterministic_record_answer"
    ai_state = ai_status.get("state", "not_configured")
    model = ""
    model_note = ""
    ai_uncertainty = ""
    follow_up_questions: list[str] = []
    evidence_facts = facts
    if ai_status.get("configured"):
        try:
            result = ai.answer_question(
                question=question,
                facts=facts[:20],
                citations=citations,
                route=route,
            )
            explanation = (
                explanation
                + "\n\nAI explanation (grounded in the documented facts above):\n"
                + result["answer"]
            )
            mode = "ai_grounded_answer"
            ai_state = "used"
            model = (result.get("meta") or {}).get("model") or ""
            ai_uncertainty = result.get("uncertainty") or ""
            follow_up_questions = [str(q) for q in (result.get("followUpQuestions") or [])][:4]
            requested = set(result.get("citations") or [])
            if requested:
                keep = [
                    c
                    for c in citations
                    if f"cite:{c.get('type')}:{c.get('id')}" in requested
                ]
                if keep:
                    citations = keep
        except ApiError as exc:
            model_note = (
                f"AI explanation unavailable ({exc.code}): {exc.message} "
                "The documented facts above are still shown from your own records."
            )
            ai_state = "error"
        except Exception as exc:  # noqa: BLE001 - provider failure must degrade, never fabricate
            model_note = (
                "AI explanation unavailable: "
                f"{getattr(exc, 'message', str(exc))} The documented facts above are still shown."
            )
            ai_state = "error"
    else:
        model_note = (
            "No external model key is configured on the API server, so this answer is deterministic record "
            "retrieval only — it is not a generated clinical explanation."
        )

    conversation = conversation_id or new_id("cnv")
    now = iso()
    record = {
        "id": new_id("ams"),
        "patient_id": patient_id,
        "conversation_id": conversation,
        "user_id": user["id"],
        "user_role": user["role"],
        "question": question[:MAX_QUESTION],
        "answer": explanation,
        "mode": mode,
        "ai_state": ai_state,
        "citations_json": json.dumps(citations[:24], separators=(",", ":")),
        "evidence_json": json.dumps(
            {
                "route": route,
                "factCount": len(evidence_facts),
                "uncertainty": ai_uncertainty,
                "followUpQuestions": follow_up_questions,
                "injectionSignals": [f["code"] for f in injection][:5],
            },
            separators=(",", ":"),
        ),
        "created_at": now,
    }
    store.create_assistant_message(record)
    if injection:
        store.create_audit(
            {
                "id": new_id("aud"),
                "patient_id": patient_id,
                "actor_user_id": user["id"],
                "actor_name": user["name"],
                "actor_role": user["role"],
                "action": "assistant.injection_suspected",
                "entity_type": "assistant_message",
                "entity_id": record["id"],
                "outcome": "allowed",
                "details_json": json.dumps(
                    {"codes": sorted({f["code"] for f in injection}), "count": len(injection)},
                    separators=(",", ":"),
                ),
                "created_at": now,
            }
        )
    store.create_audit(
        {
            "id": new_id("aud"),
            "patient_id": patient_id,
            "actor_user_id": user["id"],
            "actor_name": user["name"],
            "actor_role": user["role"],
            "action": "assistant.answered",
            "entity_type": "assistant_message",
            "entity_id": record["id"],
            "outcome": "allowed",
            "details_json": json.dumps(
                {
                    "route": route,
                    "mode": mode,
                    "aiState": ai_state,
                    "injectionSignals": len(injection),
                },
                separators=(",", ":"),
            ),
            "created_at": now,
        }
    )
    store.conn.commit()

    return {
        "id": record["id"],
        "conversationId": conversation,
        "patientId": patient_id,
        "question": question,
        "route": route,
        "mode": mode,
        "aiState": ai_state,
        "aiConfigured": bool(ai_status.get("configured")),
        "model": model,
        "modelNote": model_note,
        "facts": facts[:20],
        "explanation": explanation,
        "uncertainty": ai_uncertainty,
        "followUpQuestions": follow_up_questions,
        "citations": citations[:24],
        "containsVerifiedFacts": any(c.get("verificationStatus") == "verified" for c in citations),
        "createdAt": now,
    }


def list_conversation(
    store: Store, *, user: dict[str, Any], patient_id: str, conversation_id: str | None = None
) -> list[dict[str, Any]]:
    require_access(store, user, patient_id, "summary:read")
    rows = store.list_assistant_messages(patient_id, conversation_id=conversation_id, limit=60)
    result = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "conversationId": row["conversation_id"],
                "question": row["question"],
                "answer": row["answer"],
                "mode": row["mode"],
                "aiState": row["ai_state"],
                "citations": row.get("citations") or [],
                "evidence": row.get("evidence") or {},
                "uncertainty": (row.get("evidence") or {}).get("uncertainty") or "",
                "followUpQuestions": (row.get("evidence") or {}).get("followUpQuestions") or [],
                "requestedBy": {"id": row.get("user_id"), "role": row.get("user_role")},
                "createdAt": row["created_at"],
            }
        )
    return result
