"""End-to-end verification of the CareTwin AI document-intelligence workflows.

The script starts its **own** API process against a throwaway SQLite database and
document storage, so an automated run can never write into the persistent demo
database. It also snapshots the demo database row counts before and after and
fails if they changed. Only synthetic documents are used.

    ./apps/api/.venv/Scripts/python.exe scripts/verify_intelligence.py
"""

from __future__ import annotations

import io
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO_DB = ROOT / "data" / "demo" / "caretwin.db"
BASE = ""
PATIENT = "pat_maya"
RESULTS: list[tuple[bool, str, str]] = []

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((bool(ok), name, detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def request(path: str, user: str = "usr_maya", method: str = "GET", payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={
            "X-Demo-User-Id": user,
            "Accept": "application/json",
            "Content-Type": "application/json" if data else "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            body = res.read()
            ctype = res.headers.get("content-type", "")
            if "application/json" in ctype:
                return res.status, json.loads(body)
            return res.status, body
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, raw
    except Exception as exc:  # noqa: BLE001
        return 0, {"transportError": str(exc)}


def upload(filename: str, data: bytes, document_type: str, user: str = "usr_maya", ctype: str = "application/pdf"):
    boundary = "----caretwinverify"
    parts = []
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"documentType\"\r\n\r\n{document_type}\r\n".encode()
    )
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
        f"Content-Type: {ctype}\r\n\r\n".encode()
        + data
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    req = urllib.request.Request(
        BASE + f"/patients/{PATIENT}/documents",
        data=body,
        method="POST",
        headers={
            "X-Demo-User-Id": user,
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, {"raw": raw[:400].decode("latin-1")}


def minimal_pdf(lines: list[str]) -> bytes:
    def esc(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "[").replace(")", "]")

    body = "BT /F1 12 Tf 72 740 Td 16 TL\n"
    for line in lines:
        body += f"({esc(line)}) Tj T*\n"
    body += "ET"
    stream = body.encode("latin-1", "replace")
    objs = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n",
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        f"5 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream\nendobj\n",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = []
    for obj in objs:
        offsets.append(len(pdf))
        pdf += obj
    startxref = len(pdf)
    pdf += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n".encode()
    pdf += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF".encode()
    return pdf


def scanned_pdf(lines: list[str]) -> bytes:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1240, 700), "white")
    draw = ImageDraw.Draw(image)
    y = 60
    for line in lines:
        draw.text((60, y), line, fill="black")
        y += 60
    buf = io.BytesIO()
    image.save(buf, format="PDF")
    return buf.getvalue()


def run_checks() -> int:
    status, health = request("/health")
    check(status == 200, "API health reachable", str(health)[:160])
    ai_configured = bool(health.get("aiState") == "ready") if isinstance(health, dict) else False
    print(f"INFO aiState={health.get('aiState') if isinstance(health, dict) else '?'}")

    # ---------------------------------------------------------------- scenario A
    blood_v1 = minimal_pdf(
        [
            "SYNTHETIC DEMO REPORT - NOT A REAL PATIENT",
            "CareTwin Synthetic Labs",
            "Patient: Maya Rao    Collected: 2026-05-01",
            "Hemoglobin: 10.8 g/dL reference range 12.0-15.5",
            "WBC: 7200 /uL reference range 4000-11000",
            "Platelet count: 210 10^3/uL reference range 150-410",
            "Creatinine: 0.9 mg/dL reference range 0.6-1.3",
            "Impression: synthetic demo values for software verification",
        ]
    )
    status, uploaded = upload("SYNTHETIC-blood-2026-05-01.pdf", blood_v1, "blood_test_report")
    check(status == 200, "A1 blood report upload accepted", str(uploaded)[:200])
    doc_a = uploaded.get("document", {}) if isinstance(uploaded, dict) else {}
    doc_a_id = doc_a.get("id")
    check(doc_a.get("pageCount") == 1, "A2 one page recorded", str(doc_a.get("pageCount")))
    check("pypdf" in (doc_a.get("extractionMethod") or ""), "A3 digital text extracted via pypdf", str(doc_a.get("extractionMethod")))

    status, analysis = request(f"/patients/{PATIENT}/documents/{doc_a_id}/analysis")
    check(status == 200, "A4 analysis endpoint returns 200", str(analysis)[:200])
    values = analysis.get("values", [])
    labels = " ".join(v.get("label", "").lower() for v in values)
    check(len(values) >= 3, f"A5 values extracted ({len(values)})", str([v.get('label') for v in values]))
    hb = next((v for v in values if "hemoglobin" in v["label"].lower()), None)
    check(hb is not None and "g/dl" in (hb.get("unit") or "").lower(), "A6 hemoglobin keeps reported unit", str(hb))
    check(hb is not None and "12.0-15.5" in (hb.get("referenceRange") or ""), "A7 reported reference range preserved", str(hb.get("referenceRange") if hb else None))
    check(hb is not None and hb.get("pageNumber") == 1 and hb.get("sourceText"), "A8 page + source evidence attached")
    flags = analysis.get("findingsRequiringReview", [])
    check(any("hemoglobin" in f["label"].lower() for f in flags), "A9 out-of-printed-range value flagged for review", str([f['label'] for f in flags]))
    check(any("Hemoglobin" in t["term"] for t in analysis.get("terminology", [])), "A10 terminology explained")
    check(bool(analysis.get("questionsToAsk")), "A11 clinician questions generated", str(len(analysis.get("questionsToAsk", []))))
    check(all(v.get("verificationStatus") == "unverified" for v in values), "A12 nothing auto-verified")
    check(analysis.get("aiUsed") is False, "A13 analysis honestly reports no model use")

    if values:
        target = hb or values[0]
        status, verified = request(
            f"/patients/{PATIENT}/documents/{doc_a_id}/extractions/{target['id']}/review",
            user="usr_nandini",
            method="POST",
            payload={"action": "verify", "note": "Synthetic demo verification", "corrected_value_text": f"{target['value']}"},
        )
        check(status == 200 and verified.get("extraction", {}).get("verificationStatus") == "verified", "A14 clinician can verify an extraction", str(verified)[:200])
        twin_version = verified.get("twinVersion") if isinstance(verified, dict) else None
        status, twin = request(f"/patients/{PATIENT}/twin", user="usr_nandini")
        findings = twin.get("documentFindings", {}) if isinstance(twin, dict) else {}
        verified_rows = findings.get("verified", [])
        check(status == 200 and any(r["documentId"] == doc_a_id for r in verified_rows), "A15 verified extraction reaches the twin", str(twin_version))
        check(twin.get("version") == twin_version, "A16 twin version bumped by verification", f"{twin.get('version')} vs {twin_version}")

    # ---------------------------------------------------------------- scenario B
    prescription = minimal_pdf(
        [
            "SYNTHETIC PRESCRIPTION - NOT A REAL PATIENT",
            "Dr. Ananya Rao, MD",
            "Reg No: KMC-45192",
            "Patient: Maya Rao    Date: 2026-06-02",
            "1. Tab. Metformin 500 mg BD after food x 30 days",
            "2. Tab. Atorvastatin 10 mg HS",
            "3. Tab. Amoxicillin 250 mg TDS",
        ]
    )
    status, presc = upload("SYNTHETIC-prescription-2026-06-02.pdf", prescription, "prescription", user="usr_nandini")
    check(status == 200, "B1 prescription upload accepted", str(presc)[:200])
    presc_id = presc.get("document", {}).get("id")
    status, parsed = request(f"/patients/{PATIENT}/documents/{presc_id}/prescription")
    meds = parsed.get("medicines", []) if isinstance(parsed, dict) else []
    check(status == 200 and len(meds) >= 2, f"B2 medicines structured ({len(meds)})", str([m['name'] for m in meds]))
    metformin = next((m for m in meds if "metformin" in m["name"].lower()), None)
    check(metformin is not None and metformin.get("dosage") == "500 mg", "B3 dose captured", str(metformin))
    check(metformin is not None and metformin.get("frequency") == "twice daily", "B4 frequency interpreted", str(metformin and metformin.get("frequency")))
    check(metformin is not None and metformin.get("duration") == "30 days", "B5 duration captured")
    unclear = [m for m in meds if m.get("clarificationNeeded")]
    check(bool(unclear), "B6 unclear fields flagged for clarification", str([(m['name'], m['clarificationNeeded']) for m in meds]))
    check(parsed.get("prescriber", {}).get("name", "").startswith("Dr"), "B7 prescriber captured", str(parsed.get("prescriber")))
    status, raw_file = request(f"/patients/{PATIENT}/documents/{presc_id}/file")
    check(status == 200 and isinstance(raw_file, bytes) and raw_file.startswith(b"%PDF"), "B8 original file served for side-by-side view")
    check("does not prescribe" in parsed.get("safetyNote", ""), "B9 prescription safety note present")

    # ---------------------------------------------------------------- scenario C
    try:
        scan = scanned_pdf(
            [
                "SYNTHETIC SCANNED REPORT",
                "CareTwin Demo Imaging",
                "Patient: Maya Rao   Date: 2026-07-03",
                "Hemoglobin: 12.4 g/dL reference range 12.0-15.5",
            ]
        )
        status, ocr_doc = upload("SYNTHETIC-scanned-2026-07-03.pdf", scan, "blood_test_report")
        doc_c = ocr_doc.get("document", {}) if isinstance(ocr_doc, dict) else {}
        check(status == 200, "C1 scanned PDF upload accepted", str(ocr_doc)[:200])
        status, ocr_analysis = request(f"/patients/{PATIENT}/documents/{doc_c.get('id')}/analysis")
        summary = ocr_analysis.get("summary", {})
        pages = ocr_analysis.get("keyInformation", [])
        check(status == 200, "C2 scanned analysis returns 200")
        if summary.get("usedOcr"):
            check(True, "C3 OCR ran on scanned pages", str(summary.get("extractionMethod")))
            check(any("OCR was used" in q["basis"] for q in ocr_analysis.get("questionsToAsk", [])), "C4 OCR uncertainty surfaced")
            check(all(v.get("pageNumber") for v in ocr_analysis.get("values", [])), "C5 OCR values keep page references")
        else:
            check(False, "C3 OCR ran on scanned pages", str(summary.get("extractionError"))[:160])
    except ImportError as exc:
        print(f"SKIP scenario C: imaging libraries unavailable ({exc})")

    # ---------------------------------------------------------------- scenario D
    blood_v2 = minimal_pdf(
        [
            "SYNTHETIC DEMO REPORT - NOT A REAL PATIENT",
            "CareTwin Synthetic Labs",
            "Patient: Maya Rao    Collected: 2026-08-01",
            "Hemoglobin: 12.1 g/dL reference range 12.0-15.5",
            "WBC: 6500 /uL reference range 4000-11000",
            "Fasting Blood Glucose: 104 mg/dL reference range 70-100",
        ]
    )
    status, uploaded2 = upload("SYNTHETIC-blood-2026-08-01.pdf", blood_v2, "blood_test_report")
    check(status == 200, "D1 second compatible report uploaded", str(uploaded2)[:160])
    status, comparison = request(f"/patients/{PATIENT}/reports/comparison")
    rows = comparison.get("comparisons", []) if isinstance(comparison, dict) else []
    hb_rows = [r for r in rows if r["canonicalTest"] == "hemoglobin"]
    hb_row = next((r for r in hb_rows if r["previous"]["date"] != r["latest"]["date"]), hb_rows[0] if hb_rows else None)
    check(status == 200 and hb_row is not None, "D2 hemoglobin compared across reports", str([r["label"] for r in rows][:6]))
    check(any(r["comparable"] for r in hb_rows), "D2b at least one hemoglobin comparison is valid", str([(r["previous"]["date"], r["latest"]["date"], r["validityReasons"]) for r in hb_rows]))
    if hb_row:
        check(hb_row["previous"]["date"] != hb_row["latest"]["date"], "D3 comparison uses distinct document dates", f"{hb_row['previous']['date']}->{hb_row['latest']['date']}")
        check(abs(hb_row["difference"] - (hb_row["latest"]["value"] - hb_row["previous"]["value"])) < 1e-9, "D4 difference is arithmetic, units preserved", str(hb_row["difference"]))
        check(hb_row["previous"]["documentId"] != hb_row["latest"]["documentId"], "D5 both source documents linked")
        check("not a diagnosis" in hb_row["interpretationNote"].lower() or "does not judge" in hb_row["interpretationNote"].lower(), "D6 no diagnostic claim in comparison")
    glucose_rows = [r for r in rows if r["canonicalTest"] in {"glucose", "fasting_glucose"}]
    check(all(r["unit"] == r["latest"]["unit"] for r in rows), "D7 comparisons never mix units")
    check(bool(comparison.get("unitMismatches") is not None), "D8 unit mismatch reporting present")
    check(not any(r["canonicalTest"] == "fasting_glucose" and r["comparable"] and len([x for x in rows if x["canonicalTest"] == "fasting_glucose"]) < 2 for r in glucose_rows), "D9 fasting glucose kept distinct")

    # ---------------------------------------------------------------- scenario E
    status, answer = request(
        f"/patients/{PATIENT}/assistant/ask",
        method="POST",
        payload={"patientId": PATIENT, "question": "Explain my latest blood report"},
    )
    check(status == 200, "E1 assistant answers a blood-report question", str(answer)[:200])
    check(answer.get("aiState") == ("used" if ai_configured else "not_configured"), "E2 AI provider state reported honestly", str(answer.get("aiState")))
    check(bool(answer.get("facts")), "E3 answer contains extracted facts", str(answer.get("facts"))[:160])
    check(any(c.get("pageNumber") for c in answer.get("citations", [])), "E4 citations carry page references")
    check(all(c.get("documentName") for c in answer.get("citations", [])), "E5 citations name the source document")
    conv = answer.get("conversationId")
    check(bool(conv), "E6 conversation id returned")

    status, answer2 = request(
        f"/patients/{PATIENT}/assistant/ask",
        method="POST",
        payload={"patientId": PATIENT, "question": "What does hemoglobin mean in my report?", "conversationId": conv},
    )
    check(status == 200 and "hemoglobin" in json.dumps(answer2).lower(), "E7 terminology question answered from records")

    status, answer3 = request(
        f"/patients/{PATIENT}/assistant/ask",
        method="POST",
        payload={"patientId": PATIENT, "question": "Compare my latest hemoglobin with my previous report"},
    )
    check(status == 200 and (chr(0x2192) in (answer3.get("explanation", "") + " ".join(answer3.get("facts", []))) or "->" in (answer3.get("explanation", "") + " ".join(answer3.get("facts", [])))), "E8 comparison question returns a dated change", str(answer3.get("facts"))[:160])

    status, answer4 = request(
        f"/patients/{PATIENT}/assistant/ask",
        method="POST",
        payload={"patientId": PATIENT, "question": "Explain my prescription"},
    )
    check(status == 200 and "metformin" in json.dumps(answer4).lower(), "E9 prescription question answered from the document")

    status, answer5 = request(
        f"/patients/{PATIENT}/assistant/ask",
        method="POST",
        payload={"patientId": PATIENT, "question": "What is my vitamin D level?"},
    )
    check(status == 200 and "No uploaded document records a value for Vitamin D" in " ".join(answer5.get("facts", [])), "E10 missing data reported instead of invented", str(answer5.get("facts"))[:160])

    status, history = request(f"/patients/{PATIENT}/assistant/history?conversationId={conv}")
    check(status == 200 and len(history) >= 2, "E11 conversation history persisted", str(len(history) if isinstance(history, list) else history))

    status, caregiver = request(
        f"/patients/{PATIENT}/assistant/ask",
        user="usr_arjun",
        method="POST",
        payload={"patientId": PATIENT, "question": "Explain my latest blood report"},
    )
    check(status == 403, "E12 caregiver cannot use the assistant", str(caregiver)[:160])

    # ---------------------------------------------------------------- scenario F
    status, twin_patient = request(f"/patients/{PATIENT}/twin")
    docs = twin_patient.get("clinicalDocuments", []) if isinstance(twin_patient, dict) else []
    check(status == 200 and len(docs) >= 3, "F1 twin lists clinical documents", str(len(docs)))
    check(any(d["id"] == doc_a_id for d in docs), "F2 verified document present in the twin")
    check(twin_patient.get("documentFindings", {}).get("pendingReviewCount", 0) >= 1, "F3 pending review counted separately")
    check("does not map a document to a body region" in (twin_patient.get("bodyRegionNote") or ""), "F4 no anatomy inference claimed")
    status, events = request(f"/patients/{PATIENT}/timeline")
    event_list = events.get("events", events) if isinstance(events, dict) else events
    check(status == 200 and any("document" in json.dumps(e).lower() for e in (event_list or [])[:200]), "F5 document events on the timeline")
    check(any(e.get("verificationStatus") in {"document_extracted", "clinician_verified"} for e in (event_list or [])), "F6 timeline keeps verification status")

    # ---------------------------------------------------------------- scenario G
    status, revoked = request(f"/patients/{PATIENT}/documents/{doc_a_id}", user="usr_priya")
    check(status == 403, "G1 revoked caregiver blocked", str(revoked)[:160])
    status, other_patient = request("/patients/pat_does_not_exist/documents")
    check(status == 404, "G2 unknown patient returns 404", str(other_patient)[:160])
    status, patient_verify = request(
        f"/patients/{PATIENT}/documents/{doc_a_id}/extractions/{(values or [{}])[0].get('id', 'missing')}/review",
        method="POST",
        payload={"action": "verify"},
    )
    check(status == 403, "G3 patient cannot self-verify", str(patient_verify)[:160])
    status, audit = request(f"/patients/{PATIENT}/audit?limit=100")
    actions = {row.get("action") for row in audit} if isinstance(audit, list) else set()
    check({"document.uploaded", "document.processed", "assistant.answered"} <= actions, "G4 audit records uploads, processing and assistant use", str(sorted(actions)[:12]))
    check("document.viewed" in actions, "G5 original-file views are audited")

    # ---------------------------------------------------------------- reprocess
    status, reprocessed = request(f"/patients/{PATIENT}/documents/{doc_a_id}/reprocess", method="POST", payload=None)
    check(status == 200 and reprocessed.get("document", {}).get("processingStatus") == "processed", "H1 failed/processed document can be reprocessed", str(reprocessed.get("document", {}).get("extractionStatus")))

    failures = [r for r in RESULTS if not r[0]]
    print()
    print(f"RESULT {len(RESULTS) - len(failures)}/{len(RESULTS)} checks passed")
    for _, name, detail in failures:
        print(f"  FAILED: {name} :: {detail}")
    return 1 if failures else 0


def demo_counts() -> dict[str, int] | None:
    """Read-only snapshot of the persistent demo database."""
    if not DEMO_DB.is_file():
        return None
    conn = sqlite3.connect(f"file:{DEMO_DB.as_posix()}?mode=ro", uri=True)
    try:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("medical_documents", "document_extractions", "audit_events")
        }
    finally:
        conn.close()


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> int:
    global BASE
    temp_dir = Path(tempfile.mkdtemp(prefix="caretwin-verify-"))
    db_path = temp_dir / "verify.db"
    storage = temp_dir / "documents"
    # Safety assertion: the verification database is never the demo database.
    assert db_path.resolve() != DEMO_DB.resolve(), "verification must not use the demo database"

    before = demo_counts()
    print(f"INFO isolated database: {db_path}")
    print(f"INFO persistent demo database: {DEMO_DB.name} (read-only guard, never written)")

    port = free_port()
    env = dict(os.environ)
    env.update(
        CARETWIN_ENV="test",
        CARETWIN_DB_PATH=str(db_path),
        CARETWIN_DOCUMENT_STORAGE_PATH=str(storage),
        CARETWIN_SEED_DEMO="true",
        CARETWIN_LOG_LEVEL="WARNING",
    )
    # Provider calls are never part of deterministic verification.
    env.pop("GEMINI_API_KEY", None)

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(ROOT / "apps" / "api"),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    BASE = f"http://127.0.0.1:{port}/api/v1"
    exit_code = 1
    try:
        deadline = time.time() + 90
        while time.time() < deadline:
            status, _ = request("/health")
            if status == 200:
                break
            time.sleep(0.5)
        else:
            print("FAIL isolated verification API did not start")
            return 1
        exit_code = run_checks()
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=15)
        # Windows can hold the SQLite/storage handles for a moment after termination.
        for _ in range(6):
            shutil.rmtree(temp_dir, ignore_errors=True)
            if not temp_dir.exists():
                break
            time.sleep(0.5)

    after = demo_counts()
    if before != after:
        print("FAIL persistent demo database changed during verification")
        print(f"  before: {before}")
        print(f"  after:  {after}")
        return 1
    print(f"INFO persistent demo database unchanged: {after}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
