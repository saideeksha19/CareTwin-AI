"""Tests for document analysis, prescription parsing, comparison and assistant."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.services import document_analysis
from test_documents import build_demo_app, h, minimal_pdf


def test_reference_range_and_canonical_test_mapping():
    assert document_analysis.parse_reference_range("12.0 - 15.5") == (12.0, 15.5)
    assert document_analysis.parse_reference_range("4.0 to 11.0") == (4.0, 11.0)
    assert document_analysis.parse_reference_range("15.5 - 12.0") == (12.0, 15.5)
    assert document_analysis.parse_reference_range("Positive") is None
    assert document_analysis.parse_reference_range("") is None

    assert document_analysis.canonical_analyte("Fasting Blood Glucose") == "fasting_glucose"
    assert document_analysis.canonical_analyte("Haemoglobin (Hb)") == "hemoglobin"
    assert document_analysis.canonical_analyte("S. Creatinine") == "creatinine"
    # An unknown name must not be guessed into an existing test.
    assert document_analysis.canonical_analyte("Ceruloplasmin assay") is None


def test_prescription_parse_flags_unclear_fields():
    parsed = document_analysis.parse_prescription(
        [
            {
                "page_number": 1,
                "status": "extracted",
                "text_content": (
                    "Dr. Ananya Rao\nReg No: KMC-45192\n"
                    "1. Tab. Metformin 500 mg BD after food x 30 days\n"
                    "2. Tab. Atorvastatin 10 mg HS\n"
                ),
            }
        ]
    )
    names = [m["name"] for m in parsed["medicines"]]
    assert "Metformin" in names
    metformin = next(m for m in parsed["medicines"] if m["name"] == "Metformin")
    assert metformin["dosage"] == "500 mg"
    assert metformin["frequency"] == "twice daily"
    assert metformin["duration"] == "30 days"
    assert metformin["clarificationNeeded"] == []
    atorvastatin = next(m for m in parsed["medicines"] if m["name"] == "Atorvastatin")
    assert "duration" in atorvastatin["clarificationNeeded"]
    assert parsed["prescriber"]["registrationNumber"] == "KMC-45192"
    assert "does not prescribe" in parsed["safetyNote"]


def test_comparison_requires_same_unit_and_distinct_documents():
    def doc(doc_id: str, name: str, uploaded: str):
        return {
            "id": doc_id,
            "original_filename": name,
            "document_type": "blood_test_report",
            "uploaded_at": uploaded + "T00:00:00Z",
            "is_duplicate_of": None,
        }

    def item(item_id: str, doc_id: str, label: str, value: float, unit: str):
        return {
            "id": item_id,
            "document_id": doc_id,
            "item_type": "lab_finding",
            "label": label,
            "value_text": f"{value} {unit}",
            "value_numeric": value,
            "unit": unit,
            "reference_range": "",
            "page_number": 1,
            "verification_status": "unverified",
        }

    documents = [doc("d1", "a.pdf", "2026-01-01"), doc("d2", "b.pdf", "2026-02-01"), doc("d3", "c.pdf", "2026-03-01")]
    extractions = {
        "d1": [item("e1", "d1", "Hemoglobin", 11.0, "g/dL")],
        "d2": [item("e2", "d2", "Hemoglobin", 12.0, "g/dL")],
        # Same analyte, different unit: must never be compared with g/dL.
        "d3": [item("e3", "d3", "Hemoglobin", 130.0, "g/L")],
    }
    pages = {
        "d1": [{"page_number": 1, "status": "extracted", "text_content": "Date: 2026-01-01"}],
        "d2": [{"page_number": 1, "status": "extracted", "text_content": "Date: 2026-02-01"}],
        "d3": [{"page_number": 1, "status": "extracted", "text_content": "Date: 2026-03-01"}],
    }
    report = document_analysis.compare_reports(
        documents=documents, extractions_by_document=extractions, pages_by_document=pages
    )
    rows = report["comparisons"]
    assert len(rows) == 1, rows
    assert rows[0]["unit"] == "g/dl"
    assert rows[0]["previous"]["value"] == 11.0
    assert rows[0]["latest"]["value"] == 12.0
    assert rows[0]["difference"] == 1.0
    assert rows[0]["comparable"] is True
    assert report["unitMismatches"][0]["canonicalTest"] == "hemoglobin"


def test_analysis_endpoint_reports_values_ranges_and_page(tmp_path):
    app = build_demo_app(tmp_path)
    with TestClient(app) as client:
        pdf = minimal_pdf(
            "Patient: Maya Rao   Collected: 2026-05-01\n"
            "Hemoglobin: 10.8 g/dL reference range 12.0-15.5\n"
            "WBC: 7200 /uL reference range 4000-11000\n"
        )
        upload = client.post(
            "/api/v1/patients/pat_maya/documents",
            headers=h("patient"),
            files={"file": ("analysis.pdf", pdf, "application/pdf")},
            data={"documentType": "blood_test_report"},
        )
        assert upload.status_code == 200, upload.text
        doc_id = upload.json()["document"]["id"]

        res = client.get(f"/api/v1/patients/pat_maya/documents/{doc_id}/analysis", headers=h("patient"))
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["aiUsed"] is False
        hemoglobin = next(v for v in body["values"] if "hemoglobin" in v["label"].lower())
        assert hemoglobin["referenceRange"] == "12.0-15.5"
        assert hemoglobin["pageNumber"] == 1
        assert hemoglobin["sourceText"]
        assert any("hemoglobin" in flag["label"].lower() for flag in body["findingsRequiringReview"])
        assert any("Hemoglobin" in term["term"] for term in body["terminology"])
        assert body["questionsToAsk"]
        assert all(v["verificationStatus"] == "unverified" for v in body["values"])


def test_prescription_and_comparison_endpoints(tmp_path):
    app = build_demo_app(tmp_path)
    with TestClient(app) as client:
        prescription = minimal_pdf(
            "Dr. Ananya Rao\nReg No: KMC-45192\nTab. Metformin 500 mg BD after food x 30 days\n"
        )
        upload = client.post(
            "/api/v1/patients/pat_maya/documents",
            headers=h("clinician"),
            files={"file": ("rx.pdf", prescription, "application/pdf")},
            data={"documentType": "prescription"},
        )
        assert upload.status_code == 200, upload.text
        doc_id = upload.json()["document"]["id"]
        parsed = client.get(
            f"/api/v1/patients/pat_maya/documents/{doc_id}/prescription", headers=h("patient")
        )
        assert parsed.status_code == 200, parsed.text
        assert parsed.json()["medicines"][0]["name"] == "Metformin"

        first = minimal_pdf("Collected: 2026-05-01\nHemoglobin: 10.8 g/dL reference range 12.0-15.5\n")
        second = minimal_pdf("Collected: 2026-08-01\nHemoglobin: 12.1 g/dL reference range 12.0-15.5\n")
        for name, payload in (("first.pdf", first), ("second.pdf", second)):
            res = client.post(
                "/api/v1/patients/pat_maya/documents",
                headers=h("patient"),
                files={"file": (name, payload, "application/pdf")},
                data={"documentType": "blood_test_report"},
            )
            assert res.status_code == 200, res.text

        comparison = client.get("/api/v1/patients/pat_maya/reports/comparison", headers=h("patient"))
        assert comparison.status_code == 200, comparison.text
        rows = [r for r in comparison.json()["comparisons"] if r["canonicalTest"] == "hemoglobin"]
        assert any(r["previous"]["date"] != r["latest"]["date"] for r in rows)
        for row in rows:
            assert row["unit"] == "g/dl"
            assert "not a diagnosis" in row["interpretationNote"]


def test_assistant_is_grounded_and_role_limited(tmp_path):
    app = build_demo_app(tmp_path)
    with TestClient(app) as client:
        pdf = minimal_pdf("Collected: 2026-05-01\nHemoglobin: 10.8 g/dL reference range 12.0-15.5\n")
        client.post(
            "/api/v1/patients/pat_maya/documents",
            headers=h("patient"),
            files={"file": ("assistant.pdf", pdf, "application/pdf")},
            data={"documentType": "blood_test_report"},
        )
        answer = client.post(
            "/api/v1/patients/pat_maya/assistant/ask",
            headers=h("patient"),
            json={"patientId": "pat_maya", "question": "Explain my latest blood report"},
        )
        assert answer.status_code == 200, answer.text
        body = answer.json()
        assert body["aiState"] in {"not_configured", "used"}
        assert body["facts"]
        assert any(c["pageNumber"] for c in body["citations"])
        assert body["mode"].startswith("deterministic")

        missing = client.post(
            "/api/v1/patients/pat_maya/assistant/ask",
            headers=h("patient"),
            json={"patientId": "pat_maya", "question": "What is my vitamin D level?"},
        )
        assert missing.status_code == 200
        assert any("No uploaded document" in fact for fact in missing.json()["facts"])

        caregiver = client.post(
            "/api/v1/patients/pat_maya/assistant/ask",
            headers=h("caregiver"),
            json={"patientId": "pat_maya", "question": "Explain my latest blood report"},
        )
        assert caregiver.status_code == 403

        history = client.get("/api/v1/patients/pat_maya/assistant/history", headers=h("patient"))
        assert history.status_code == 200
        assert len(history.json()) >= 2
