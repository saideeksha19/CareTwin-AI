from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.utils import iso, new_id


@dataclass
class PageText:
    page_number: int
    text: str
    status: str
    method: str
    error: str = ""


def _tesseract_cmd() -> str | None:
    import os

    configured = (os.getenv("CARETWIN_TESSERACT_CMD") or os.getenv("TESSERACT_CMD") or "").strip()
    if configured:
        p = Path(configured)
        if p.exists():
            return str(p)
    found = shutil.which("tesseract")
    if found:
        return found
    # Common installer locations are checked so OCR works without extra setup.
    for candidate in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/opt/homebrew/bin/tesseract",
    ):
        if Path(candidate).exists():
            return candidate
    return None


def _capability_report() -> dict[str, Any]:
    has_pypdf = False
    has_pdfplumber = False
    tesseract_cmd = _tesseract_cmd()
    has_tesseract = bool(tesseract_cmd)
    has_pytesseract = False
    try:
        import pypdf  # type: ignore
        has_pypdf = True
    except Exception:
        pass
    try:
        import pdfplumber  # type: ignore
        has_pdfplumber = True
    except Exception:
        pass
    try:
        import pytesseract  # type: ignore
        has_pytesseract = True
    except Exception:
        pass
    return {
        "pypdf": has_pypdf,
        "pdfplumber": has_pdfplumber,
        "tesseractBinary": has_tesseract,
        "pytesseract": has_pytesseract,
        "ocrAvailable": bool(has_tesseract and has_pytesseract),
        "digitalPdfExtractionAvailable": bool(has_pypdf or has_pdfplumber),
    }


def _pdf_renderer_available() -> bool:
    try:
        import pypdfium2  # type: ignore  # noqa: F401

        return True
    except Exception:
        return False


def _ocr_pdf_page_image(pdf, page_index: int, dpi_scale: float = 150 / 72):
    """Render a single PDF page to a PIL image using pypdfium2. Caller must close image."""
    page = pdf[page_index]
    try:
        bitmap = page.render(scale=dpi_scale)
        try:
            image = bitmap.to_pil()
        finally:
            try:
                bitmap.close()
            except Exception:
                pass
        return image
    finally:
        try:
            page.close()
        except Exception:
            pass


def _ocr_text_from_pil_image(image) -> str:
    import pytesseract  # type: ignore

    cmd = _tesseract_cmd()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    return (pytesseract.image_to_string(image) or "").strip()


def _apply_scanned_pdf_ocr(storage_path: str, pages: list[PageText], max_pages: int) -> tuple[list[PageText], list[str]]:
    """For pages without extractable digital text, attempt per-page PDF render + Tesseract OCR.

    Processes pages independently (one render/image in memory at a time) and never raises.
    Returns (pages, notes).
    """
    caps = _capability_report()
    notes: list[str] = []
    needs_ocr = [i for i, p in enumerate(pages) if p.status == "empty_or_unreadable" and not (p.text or "").strip()]
    if not needs_ocr:
        return pages, notes

    if not caps["ocrAvailable"]:
        limitation = (
            "OCR is unavailable for scanned PDF pages: Tesseract OCR binary and/or pytesseract+Pillow not installed/configured. "
            "Install/configure Tesseract and ensure Python deps `pytesseract` and `Pillow` are available."
        )
        for i in needs_ocr:
            p = pages[i]
            p.error = (p.error + " " + limitation).strip() if p.error else limitation
        notes.append(limitation)
        return pages, notes

    if not _pdf_renderer_available():
        limitation = (
            "Scanned PDF OCR unavailable: no PDF rendering library detected (expected `pypdfium2`). "
            "Install with: `./apps/api/.venv/Scripts/python.exe -m pip install pypdfium2` to render pages for OCR."
        )
        for i in needs_ocr:
            p = pages[i]
            p.error = (p.error + " " + limitation).strip() if p.error else limitation
        notes.append(limitation)
        return pages, notes

    pdf = None
    try:
        import pypdfium2 as pdfium  # type: ignore

        pdf = pdfium.PdfDocument(storage_path)
    except Exception as exc:
        msg = f"Scanned PDF OCR unavailable: failed to open PDF for rendering: {exc}"
        for i in needs_ocr:
            p = pages[i]
            p.error = (p.error + " " + msg).strip() if p.error else msg
        notes.append(msg)
        return pages, notes

    try:
        page_count = len(pdf)
        for i in needs_ocr:
            p = pages[i]
            page_index = p.page_number - 1
            if page_index < 0 or page_index >= page_count:
                p.error = (p.error + " OCR skipped: page index out of range for renderer.").strip()
                continue
            image = None
            try:
                # Moderate DPI for 8GB-RAM safety; one page/image at a time.
                image = _ocr_pdf_page_image(pdf, page_index, dpi_scale=150 / 72)
                text = _ocr_text_from_pil_image(image)
                if text:
                    p.text = text
                    p.status = "extracted"
                    p.method = "pypdf_text+tesseract_pdf_ocr"
                    p.error = ""
                else:
                    p.status = "empty_or_unreadable"
                    p.method = "pypdf_text+tesseract_pdf_ocr"
                    p.error = "OCR completed on scanned PDF page but no readable text was detected."
            except Exception as exc:
                # Keep page-level error; do not invalidate other pages.
                p.status = "error"
                p.method = "pypdf_text+tesseract_pdf_ocr"
                p.error = f"OCR failed for scanned PDF page: {exc}"
            finally:
                try:
                    if image is not None:
                        image.close()
                except Exception:
                    pass
    finally:
        try:
            if pdf is not None:
                pdf.close()
        except Exception:
            pass

    return pages, notes


def extract_pdf_pages(storage_path: str, max_pages: int = 50) -> tuple[list[PageText], str, str | None]:
    caps = _capability_report()
    path = Path(storage_path)
    pages: list[PageText] = []
    method = ""
    global_error: str | None = None

    # Prefer pypdf for digital text
    if caps["pypdf"]:
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            total = len(reader.pages)
            method = "pypdf_text"
            for idx, page in enumerate(reader.pages[:max_pages], start=1):
                try:
                    text = (page.extract_text() or "").strip()
                    if text:
                        pages.append(PageText(idx, text, "extracted", method))
                    else:
                        pages.append(PageText(idx, "", "empty_or_unreadable", method, "No extractable text on page (may be scanned)."))
                except Exception as exc:
                    pages.append(PageText(idx, "", "error", method, f"Page extraction failed: {exc}"))
            if total > max_pages:
                global_error = f"Document truncated to first {max_pages} of {total} pages."
            if not pages:
                pages = [PageText(1, "", "empty_or_unreadable", method, "No extractable text found.")]

            # For pages without digital text, attempt scanned-page OCR (per-page, memory-conscious).
            pages, ocr_notes = _apply_scanned_pdf_ocr(str(path), pages, max_pages)
            if ocr_notes:
                global_error = (global_error + " " + " ".join(ocr_notes)).strip() if global_error else " ".join(ocr_notes)
            methods_used = sorted({p.method for p in pages if p.method})
            if "tesseract_pdf_ocr" in "+".join(methods_used):
                method = "pypdf_text+pdf_page_ocr" if len(methods_used) > 1 else "pypdf_text+pdf_page_ocr"
            return pages, method, global_error
        except Exception as exc:
            global_error = f"PDF text extraction failed with pypdf: {exc}"

    # Fallback: best-effort raw text scan (limited, explicit)
    try:
        raw = path.read_bytes()
        # very naive extraction of parenthesized text tokens; not reliable for all PDFs
        chunks = re.findall(rb"\((?:\\.|[^\\)]){3,200}\)", raw)
        texts = []
        for c in chunks:
            try:
                s = c[1:-1].decode("latin-1", errors="ignore")
                s = re.sub(r"\\[nrtbf()\\]", " ", s)
                s = re.sub(r"\s+", " ", s).strip()
                if len(s) >= 3:
                    texts.append(s)
            except Exception:
                continue
        joined = "\n".join(texts[:500]).strip()
        if joined:
            pages = [PageText(1, joined, "extracted_partial", "pdf_raw_fallback", "Best-effort fallback extraction without a PDF parser; page boundaries unavailable.")]
            method = "pdf_raw_fallback"
            note = "Digital PDF parser library unavailable (install `pypdf` in apps/api venv). Used limited fallback extraction."
            global_error = (global_error + " " + note).strip() if global_error else note
            return pages, method, global_error
    except Exception as exc:
        global_error = (global_error + f" Fallback extraction failed: {exc}").strip() if global_error else f"Fallback extraction failed: {exc}"

    if caps["pypdf"] or caps["pdfplumber"]:
        limitation = (
            "Digital PDF text extraction failed: a PDF parser is installed, but it could not read this file. "
            "The document may be corrupt or use an unsupported structure. The original file is preserved; "
            "try reprocessing after checking it opens in a PDF viewer."
        )
    else:
        limitation = (
            "Digital PDF text extraction is unavailable: no PDF parser library detected (expected `pypdf` or `pdfplumber`). "
            "Install with: `./apps/api/.venv/Scripts/python.exe -m pip install pypdf` (or add to apps/api/requirements.txt) and retry processing."
        )
    pages = [PageText(1, "", "unavailable", "unavailable", limitation)]
    if global_error:
        limitation = global_error + " " + limitation
        pages[0].error = limitation
    return pages, "unavailable", limitation


def extract_image_pages(storage_path: str) -> tuple[list[PageText], str, str | None]:
    caps = _capability_report()
    path = Path(storage_path)
    if caps["ocrAvailable"]:
        try:
            import pytesseract  # type: ignore
            from PIL import Image  # type: ignore

            cmd = _tesseract_cmd()
            if cmd:
                pytesseract.pytesseract.tesseract_cmd = cmd
            image = Image.open(path)
            text = (pytesseract.image_to_string(image) or "").strip()
            status = "extracted" if text else "empty_or_unreadable"
            err = "" if text else "OCR completed but no readable text was detected."
            return [PageText(1, text, status, "tesseract_ocr", err)], "tesseract_ocr", None
        except Exception as exc:
            msg = f"OCR failed: {exc}"
            return [PageText(1, "", "error", "tesseract_ocr", msg)], "tesseract_ocr", msg

    limitation = (
        "OCR is unavailable: Tesseract OCR binary and/or pytesseract+Pillow not installed. "
        "Install Tesseract (https://github.com/tesseract-ocr/tesseract) and ensure `tesseract` is on PATH, "
        "then install Python deps: `./apps/api/.venv/Scripts/python.exe -m pip install pytesseract pillow`."
    )
    return [PageText(1, "", "unavailable", "unavailable", limitation)], "unavailable", limitation


_LAB_LINE = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z0-9 /\-\(\)]{2,40})\s*[:\-]\s*"
    r"(?P<val>-?\d+(?:\.\d+)?)\s*(?P<unit>[A-Za-z/%0-9\^\u00b5]+)?"
)

# A printed range is a strict two-ended numeric interval, optionally followed by a
# unit token. It is matched *after* the value instead of inside one greedy pattern,
# so adjacent labels on a dense single-line report cannot leak into the range.
_RANGE_AFTER = re.compile(
    r"\s*(?:ref(?:erence)?\s*(?:range|interval)|range)\s*[:\-]?\s*"
    r"(?P<low>\d+(?:\.\d+)?)\s*[-\u2013]\s*(?P<high>\d+(?:\.\d+)?)"
    r"(?:\s*(?P<unit>[A-Za-z%0-9\^\u00b5/]{1,12}))?"
)

_RANGE_UNIT_WORDS = {
    "g", "mg", "mcg", "ml", "l", "dl", "iu", "u", "sec", "fl", "pg", "ng",
    "ratio", "mmol", "umol", "\u00b5mol", "meq", "miu", "uiu", "cells", "ul",
}


def _looks_like_unit(token: str) -> bool:
    """True only for tokens that look like a measurement unit, never a label."""
    cleaned = (token or "").strip()
    if not cleaned:
        return False
    if re.search(r"[\d/%^\u00b5]", cleaned):
        return True
    return cleaned.lower() in _RANGE_UNIT_WORDS


def _printed_range(text: str, start: int) -> str:
    """Extract the printed reference range immediately following a value."""
    match = _RANGE_AFTER.match(text, start)
    if not match:
        return ""
    printed = f"{match.group('low')}-{match.group('high')}"
    unit = (match.group("unit") or "").strip()
    if unit and _looks_like_unit(unit):
        printed = f"{printed} {unit}"
    return printed


def build_structured_extractions(document: dict[str, Any], pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic, conservative extraction from available text. Never invents values."""
    items: list[dict[str, Any]] = []
    now = iso()
    for page in pages:
        text = (page.get("text_content") or "").strip()
        page_no = int(page.get("page_number") or 1)
        status = page.get("status") or "pending"
        if not text or status in {"unavailable", "error", "pending"}:
            continue
        # Dates
        for m in re.finditer(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", text):
            src = m.group(1)
            items.append(_item(document, "document_date", "Document date mention", src, None, "", "", "", page_no, _context(text, m.start(), m.end()), "extracted", "Date mentioned in document text; requires clinician review for meaning."))
            if len([i for i in items if i["item_type"] == "document_date"]) >= 5:
                break
        # Lab-like results: "Test: value unit [reference range low-high]"
        for m in _LAB_LINE.finditer(text):
            name = m.group("name").strip()
            # A trailing unit from the previous value can begin the match (for example
            # "g/dL Creatinine: 0.9"); it is a unit, never part of the label.
            tokens = name.split()
            while len(tokens) > 1 and _looks_like_unit(tokens[0]):
                tokens.pop(0)
            name = " ".join(tokens)
            val = m.group("val")
            unit = (m.group("unit") or "").strip()
            rng = _printed_range(text, m.end())
            lowered_name = name.lower()
            if len(name) < 3 or lowered_name in {"page", "date", "phone", "fax"}:
                continue
            # Administrative lines (patient name / collected / reported) are not lab results.
            if re.search(r"\b(patient|collected|reported|sample|doctor|hospital|clinic|lab|laboratory|caretwin|synthetic|printed|accession)\b", lowered_name):
                continue
            # A bare year with no unit is a date fragment, not a measurement.
            if not unit and re.fullmatch(r"(?:19|20)\d{2}", val):
                continue
            # A measurement needs a unit or a printed reference range to be meaningful.
            if not unit and not rng:
                continue
            try:
                num = float(val)
            except Exception:
                num = None
            items.append(_item(document, "lab_finding", name, val + (f" {unit}" if unit else ""), num, unit, rng, "", page_no, _context(text, m.start(), m.end()), "extracted", "Pattern-extracted value/unit/range as written; unverified and may be incomplete."))
            if len([i for i in items if i["item_type"] == "lab_finding"]) >= 40:
                break
        # Medications (conservative): lines with a dose form or strength word.
        for line in [ln.strip() for ln in re.split(r"[\n\r]+", text) if ln.strip()]:
            # A lab result line such as "Hemoglobin: 10.8 g/dL reference range 12.0-15.5"
            # contains "g" but is not a medicine instruction.
            is_lab_line = bool(
                re.match(r"^[A-Za-z][A-Za-z0-9 /\-\(\)]{2,40}\s*[:\-]\s*-?\d", line)
                or re.search(r"reference range|ref\.?\s*range|reference interval", line, re.I)
            )
            has_dose_form = bool(
                re.search(r"\b(tablet|tab|tabs|capsule|caps|cap|inhaler|inhalation|puff|puffs|syrup|syp|drops?|ointment|cream|sachet|injection|inj)\b", line, re.I)
            )
            has_strength = bool(re.search(r"\b\d+(?:\.\d+)?\s?(?:mg|mcg|\u00b5g|ml|iu|units?)\b", line, re.I))
            has_frequency = bool(re.search(r"\b(od|bd|bid|tds|tid|qid|qds|hs|sos|prn|1-0-1|0-0-1|1-1-1|once|twice|thrice|daily|every)\b", line, re.I))
            if is_lab_line:
                continue
            if (has_dose_form or (has_strength and has_frequency)) and re.search(r"[A-Za-z]{3,}", line):
                if len(line) > 240:
                    continue
                items.append(_item(document, "medication_mention", "Medication/instruction mention", line, None, "", "", "", page_no, line, "uncertain", "Possible medication or instruction text detected; requires clinician verification. Do not treat as confirmed dose."))  # noqa: E501
            if len([i for i in items if i["item_type"] == "medication_mention" and i["page_number"] == page_no]) >= 20:
                break
        # Discharge/follow-up/precaution keywords (capture line as documented text)
        keyword_map = [
            ("follow_up", r"\b(follow[- ]?up|appointment|review on|return to)\b"),
            ("precaution", r"\b(precaution|warning|seek care|emergency|call|avoid)\b"),
            ("diagnosis_text", r"\b(diagnosis|impression|assessment)\b"),
            ("discharge_instruction", r"\b(discharge|instructions|advice|plan)\b"),
        ]
        for line in [ln.strip() for ln in re.split(r"[\n\r]+", text) if ln.strip()]:
            if len(line) < 12 or len(line) > 300:
                continue
            for item_type, pattern in keyword_map:
                if re.search(pattern, line, re.I):
                    label = {
                        "follow_up": "Follow-up mention",
                        "precaution": "Precaution/warning mention",
                        "diagnosis_text": "Diagnosis/impression text",
                        "discharge_instruction": "Discharge instruction mention",
                    }[item_type]
                    items.append(_item(document, item_type, label, line, None, "", "", "", page_no, line, "uncertain", "Text contains relevant clinical keywords as written; unverified."))
                    break
            if len([i for i in items if i["page_number"] == page_no and i["item_type"] in {k for k, _ in keyword_map}]) >= 20:
                break
    # de-duplicate by (type,label,value,page,source)
    seen = set()
    deduped = []
    for item in items:
        key = (item["item_type"], item["label"], item["value_text"], item["page_number"], item["source_text"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:200]


def _context(text: str, start: int, end: int, window: int = 80) -> str:
    s = max(0, start - window)
    e = min(len(text), end + window)
    snippet = text[s:e].replace("\n", " ").strip()
    return re.sub(r"\s+", " ", snippet)[:500]


def _item(document, item_type, label, value_text, value_numeric, unit, reference_range, abnormal_flag, page_number, source_text, extraction_status, confidence_note):
    now = iso()
    payload = {
        "itemType": item_type,
        "label": label,
        "valueText": value_text,
        "valueNumeric": value_numeric,
        "unit": unit,
        "referenceRange": reference_range,
        "abnormalFlag": abnormal_flag,
        "pageNumber": page_number,
        "sourceText": source_text,
        "extractionStatus": extraction_status,
    }
    return {
        "id": new_id("dxe"),
        "document_id": document["id"],
        "patient_id": document["patient_id"],
        "item_type": item_type,
        "label": label,
        "value_text": value_text or "",
        "value_numeric": value_numeric,
        "unit": unit or "",
        "reference_range": reference_range or "",
        "abnormal_flag": abnormal_flag or "",
        "page_number": page_number,
        "source_text": source_text or "",
        "extraction_status": extraction_status,
        "verification_status": "unverified",
        "confidence_note": confidence_note or "",
        "evidence_id": None,
        "verified_by_user_id": None,
        "verified_by_name": None,
        "verified_at": None,
        "rejected_by_user_id": None,
        "rejected_by_name": None,
        "rejected_at": None,
        "review_note": "",
        "corrected_value_text": None,
        "original_payload_json": json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
        "created_at": now,
        "updated_at": now,
    }
