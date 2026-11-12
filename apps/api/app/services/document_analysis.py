from __future__ import annotations

import re
from typing import Any

from app.utils import iso

# ---------------------------------------------------------------------------
# Educational terminology. Descriptions explain what a term *measures* only.
# No thresholds, ranges or "normal/abnormal" claims live in this table: any
# range shown to the reader must come from the uploaded report itself.
# ---------------------------------------------------------------------------

ANALYTE_GUIDE: dict[str, dict[str, str]] = {
    "hemoglobin": {
        "label": "Hemoglobin",
        "explanation": "Hemoglobin is the oxygen-carrying protein inside red blood cells. A hemoglobin value describes how much of this protein is present in a measured volume of blood.",
    },
    "hematocrit": {
        "label": "Hematocrit",
        "explanation": "Hematocrit describes what share of the blood volume is made up of red blood cells.",
    },
    "rbc": {
        "label": "Red blood cell count",
        "explanation": "The red blood cell count reports how many red blood cells are present in a measured volume of blood.",
    },
    "wbc": {
        "label": "White blood cell count",
        "explanation": "White blood cells are part of the body's immune response; this count reports how many are present in a measured volume of blood.",
    },
    "platelet": {
        "label": "Platelet count",
        "explanation": "Platelets are cell fragments involved in blood clotting; this count reports how many are present.",
    },
    "mcv": {
        "label": "MCV (mean corpuscular volume)",
        "explanation": "MCV describes the average size of the red blood cells in the sample.",
    },
    "mch": {
        "label": "MCH (mean corpuscular hemoglobin)",
        "explanation": "MCH describes the average amount of hemoglobin inside each red blood cell.",
    },
    "neutrophil": {
        "label": "Neutrophils",
        "explanation": "Neutrophils are a type of white blood cell; the report gives their count or percentage in the sample.",
    },
    "lymphocyte": {
        "label": "Lymphocytes",
        "explanation": "Lymphocytes are a type of white blood cell involved in immune responses.",
    },
    "eosinophil": {
        "label": "Eosinophils",
        "explanation": "Eosinophils are a type of white blood cell often discussed in the context of allergy and infection responses.",
    },
    "glucose": {
        "label": "Glucose",
        "explanation": "Glucose is the main sugar circulating in blood and is used by cells for energy. Reports often state whether the sample was fasting or taken at another time, which matters when comparing readings.",
    },
    "hba1c": {
        "label": "HbA1c (glycated hemoglobin)",
        "explanation": "HbA1c reflects the share of hemoglobin that has glucose attached to it, and reports describe it as an indication of average blood sugar over the preceding weeks.",
    },
    "creatinine": {
        "label": "Creatinine",
        "explanation": "Creatinine is a waste product normally filtered by the kidneys, so reports use it as an indicator of kidney filtration.",
    },
    "egfr": {
        "label": "eGFR (estimated glomerular filtration rate)",
        "explanation": "eGFR is a calculated estimate of how much blood the kidneys filter per minute, derived from creatinine and other factors.",
    },
    "urea": {
        "label": "Blood urea / BUN",
        "explanation": "Urea is a waste product formed when the body breaks down protein; it is cleared by the kidneys.",
    },
    "sodium": {
        "label": "Sodium",
        "explanation": "Sodium is an electrolyte that helps regulate the body's fluid balance and nerve and muscle function.",
    },
    "potassium": {
        "label": "Potassium",
        "explanation": "Potassium is an electrolyte involved in nerve signalling and heart and muscle function.",
    },
    "chloride": {
        "label": "Chloride",
        "explanation": "Chloride is an electrolyte that works alongside sodium in maintaining fluid and acid-base balance.",
    },
    "calcium": {
        "label": "Calcium",
        "explanation": "Calcium is a mineral involved in bone structure, muscle contraction and nerve signalling.",
    },
    "alt": {
        "label": "ALT (alanine aminotransferase)",
        "explanation": "ALT is an enzyme found mainly in liver cells; reports measure it as an indicator of liver cell activity.",
    },
    "ast": {
        "label": "AST (aspartate aminotransferase)",
        "explanation": "AST is an enzyme present in the liver and muscle; reports measure it as an indicator of tissue activity.",
    },
    "bilirubin": {
        "label": "Bilirubin",
        "explanation": "Bilirubin is a yellow pigment produced when red blood cells are broken down and processed by the liver.",
    },
    "albumin": {
        "label": "Albumin",
        "explanation": "Albumin is a protein made by the liver that helps keep fluid in the blood vessels and carries substances through the bloodstream.",
    },
    "tsh": {
        "label": "TSH (thyroid stimulating hormone)",
        "explanation": "TSH is a hormone released by the pituitary gland that signals the thyroid gland to produce thyroid hormones.",
    },
    "t3": {
        "label": "T3 (triiodothyronine)",
        "explanation": "T3 is a thyroid hormone involved in regulating how the body uses energy.",
    },
    "t4": {
        "label": "T4 (thyroxine)",
        "explanation": "T4 is the main hormone produced by the thyroid gland and is converted to T3 in the body.",
    },
    "cholesterol": {
        "label": "Total cholesterol",
        "explanation": "Cholesterol is a fat-like substance carried in the blood; the report gives the total amount measured.",
    },
    "ldl": {
        "label": "LDL cholesterol",
        "explanation": "LDL is one of the lipoproteins that carry cholesterol through the blood.",
    },
    "hdl": {
        "label": "HDL cholesterol",
        "explanation": "HDL is one of the lipoproteins that carry cholesterol through the blood.",
    },
    "triglyceride": {
        "label": "Triglycerides",
        "explanation": "Triglycerides are a form of stored fat transported in the blood.",
    },
    "crp": {
        "label": "C-reactive protein",
        "explanation": "CRP is a protein produced by the liver whose level can change with inflammation in the body.",
    },
    "esr": {
        "label": "ESR (erythrocyte sedimentation rate)",
        "explanation": "ESR measures how quickly red blood cells settle in a tube, which reports use as a general marker of inflammation.",
    },
    "ferritin": {
        "label": "Ferritin",
        "explanation": "Ferritin is a protein that stores iron inside cells; reports use it as an indicator of the body's iron stores.",
    },
    "vitamin d": {
        "label": "Vitamin D",
        "explanation": "Vitamin D is involved in calcium absorption and bone health; the report gives the measured level.",
    },
    "vitamin b12": {
        "label": "Vitamin B12",
        "explanation": "Vitamin B12 is needed for nerve function and red blood cell formation; the report gives the measured level.",
    },
    "uric acid": {
        "label": "Uric acid",
        "explanation": "Uric acid is a waste product formed when the body breaks down purines, cleared through the kidneys.",
    },
    "inr": {
        "label": "INR (international normalized ratio)",
        "explanation": "INR standardises a clotting time measurement so results from different laboratories can be compared.",
    },
    "troponin": {
        "label": "Troponin",
        "explanation": "Troponin is a protein released from heart muscle cells; reports measure it as an indicator of heart muscle status.",
    },
    "d-dimer": {
        "label": "D-dimer",
        "explanation": "D-dimer is a fragment produced when blood clots are broken down, measured in blood.",
    },
    "amylase": {
        "label": "Amylase",
        "explanation": "Amylase is an enzyme produced by the pancreas and salivary glands that helps break down carbohydrates.",
    },
    "lipase": {
        "label": "Lipase",
        "explanation": "Lipase is an enzyme produced by the pancreas that helps digest fats.",
    },
}

DOCUMENT_GLOSSARY: list[tuple[str, str]] = [
    (
        r"reference range|reference interval|normal range|ref\.?\s*range",
        "Reference range: the interval printed on this report for that test. Ranges differ between laboratories and populations, so only the range printed on your own report is shown here.",
    ),
    (r"\bimpression\b", "Impression: the summarising section of a radiology or clinical report describing the reporting clinician's interpretation."),
    (r"\bfindings?\b", "Findings: the section where the reporting clinician describes what was observed in the examination or test."),
    (r"\bNAD\b", "NAD: shorthand for 'no abnormality detected', as written by the reporting clinician."),
    (r"\bOD\b", "OD: abbreviation for once daily (one dose per day) when used in a prescription."),
    (r"\bBD\b|\bBID\b", "BD/BID: abbreviations for twice daily."),
    (r"\bTDS\b|\bTID\b", "TDS/TID: abbreviations for three times daily."),
    (r"\bQID\b|\bQDS\b", "QID/QDS: abbreviations for four times daily."),
    (r"\bHS\b", "HS: abbreviation for at bedtime."),
    (r"\bSOS\b|\bPRN\b", "SOS/PRN: taken only when needed, as written on the prescription."),
    (r"\bAC\b", "AC: before food."),
    (r"\bPC\b", "PC: after food."),
    (r"\bstat\b", "stat: to be taken or done immediately, as written."),
]

FIRST_LINE_RE = re.compile(r"^[ \t]*([A-Za-z][A-Za-z .'\-]{1,60})$", re.MULTILINE)

_UNIT_ALIASES = {
    "gm/dl": "g/dl",
    "g/dl": "g/dl",
    "g%": "g/dl",
    "mg/dl": "mg/dl",
    "mmol/l": "mmol/l",
    "meq/l": "meq/l",
    "miu/l": "miu/l",
    "uiu/ml": "uiu/ml",
    "u/l": "u/l",
    "iu/l": "iu/l",
    "ng/ml": "ng/ml",
    "pg/ml": "pg/ml",
    "10^3/ul": "10^3/ul",
    "10^6/ul": "10^6/ul",
    "cells/ul": "cells/ul",
    "/ul": "/ul",
    "%": "%",
    "fl": "fl",
    "pg": "pg",
    "sec": "sec",
    "ratio": "ratio",
}


def _norm_unit(unit: str) -> str:
    cleaned = re.sub(r"\s+", "", (unit or "").lower())
    if not cleaned:
        return ""
    return _UNIT_ALIASES.get(cleaned, cleaned)


# ---------------------------------------------------------------------------
# Canonical analyte identity. Comparison is only ever offered between the same
# canonical key *and* the same normalised unit, so a fasting glucose report is
# never compared with a random glucose report.
# ---------------------------------------------------------------------------

_ANALYTE_PATTERNS: list[tuple[str, str]] = [
    ("hba1c", r"hba1c|glycated h(?:a)?emoglobin|glycosylated h(?:a)?emoglobin"),
    ("fasting_glucose", r"(?:fasting|fbs|fbg)\s*(?:blood\s*)?(?:glucose|sugar)"),
    ("postprandial_glucose", r"(?:post\s*prandial|ppbs|ppbg|2\s*h(?:ou)?r)\s*(?:blood\s*)?(?:glucose|sugar)"),
    ("glucose", r"(?:random\s*)?(?:blood\s*)?(?:glucose|sugar)"),
    ("egfr", r"egfr|gfr"),
    ("hemoglobin", r"h(?:a)?emoglobin|\bhb\b"),
    ("hematocrit", r"h(?:a)?ematocrit|\bpcv\b|\bhct\b"),
    ("wbc", r"\bwbc\b|white\s*(?:blood\s*)?cell|total\s*leucocyte|tlc"),
    ("platelet", r"platelet|thrombocyte"),
    ("rbc", r"\brbc\b|red\s*(?:blood\s*)?cell"),
    ("mcv", r"\bmcv\b"),
    ("mchc", r"\bmchc\b"),
    ("mch", r"\bmch\b"),
    ("neutrophil", r"neutrophil"),
    ("lymphocyte", r"lymphocyte"),
    ("eosinophil", r"eosinophil"),
    ("monocyte", r"monocyte"),
    ("basophil", r"basophil"),
    ("creatinine", r"creatinine"),
    ("urea", r"\burea\b|\bbun\b"),
    ("sodium", r"\bsodium\b|\bna\+?\b"),
    ("potassium", r"\bpotassium\b|\bk\+?\b"),
    ("chloride", r"\bchloride\b"),
    ("bicarbonate", r"bicarbonate|\bhco3\b"),
    ("calcium", r"\bcalcium\b"),
    ("phosphorus", r"phosphorus|phosphate"),
    ("alt", r"\balt\b|sgpt|alanine\s*aminotransferase"),
    ("ast", r"\bast\b|sgot|aspartate\s*aminotransferase"),
    ("alp", r"\balp\b|alkaline\s*phosphatase"),
    ("ggt", r"\bggt\b|gamma\s*gt"),
    ("bilirubin", r"bilirubin"),
    ("albumin", r"\balbumin\b"),
    ("total_protein", r"total\s*protein"),
    ("tsh", r"\btsh\b|thyroid\s*stimulating"),
    ("t3", r"\bt3\b|triiodothyronine"),
    ("t4", r"\bt4\b|thyroxine"),
    ("cholesterol", r"total\s*cholesterol|cholesterol\s*,?\s*total|^cholesterol$"),
    ("ldl", r"\bldl\b"),
    ("hdl", r"\bhdl\b"),
    ("triglyceride", r"triglyceride"),
    ("crp", r"\bcrp\b|c[\s-]*reactive\s*protein"),
    ("esr", r"\besr\b|sedimentation"),
    ("ferritin", r"ferritin"),
    ("vitamin_d", r"vitamin\s*d|25[\s-]*oh"),
    ("vitamin_b12", r"vitamin\s*b[\s-]*12|\bb12\b"),
    ("uric_acid", r"uric\s*acid"),
    ("inr", r"\binr\b"),
    ("troponin", r"troponin"),
    ("d_dimer", r"d[\s-]*dimer"),
    ("amylase", r"amylase"),
    ("lipase", r"lipase"),
]

_GLOSSARY_KEY_BY_CANONICAL = {
    "hba1c": "hba1c",
    "fasting_glucose": "glucose",
    "postprandial_glucose": "glucose",
    "glucose": "glucose",
    "egfr": "egfr",
    "hemoglobin": "hemoglobin",
    "hematocrit": "hematocrit",
    "wbc": "wbc",
    "platelet": "platelet",
    "rbc": "rbc",
    "mcv": "mcv",
    "mch": "mch",
    "neutrophil": "neutrophil",
    "lymphocyte": "lymphocyte",
    "eosinophil": "eosinophil",
    "creatinine": "creatinine",
    "urea": "urea",
    "sodium": "sodium",
    "potassium": "potassium",
    "chloride": "chloride",
    "calcium": "calcium",
    "alt": "alt",
    "ast": "ast",
    "bilirubin": "bilirubin",
    "albumin": "albumin",
    "tsh": "tsh",
    "t3": "t3",
    "t4": "t4",
    "cholesterol": "cholesterol",
    "ldl": "ldl",
    "hdl": "hdl",
    "triglyceride": "triglyceride",
    "crp": "crp",
    "esr": "esr",
    "ferritin": "ferritin",
    "vitamin_d": "vitamin d",
    "vitamin_b12": "vitamin b12",
    "uric_acid": "uric acid",
    "inr": "inr",
    "troponin": "troponin",
    "d_dimer": "d-dimer",
    "amylase": "amylase",
    "lipase": "lipase",
}


def canonical_analyte(label: str) -> str | None:
    text = (label or "").strip().lower()
    if not text:
        return None
    for key, pattern in _ANALYTE_PATTERNS:
        if re.search(pattern, text):
            return key
    return None


def analyte_display_name(canonical: str) -> str:
    glossary_key = _GLOSSARY_KEY_BY_CANONICAL.get(canonical)
    if glossary_key and glossary_key in ANALYTE_GUIDE:
        return ANALYTE_GUIDE[glossary_key]["label"]
    return canonical.replace("_", " ")


def analyte_explanation(canonical: str) -> str | None:
    glossary_key = _GLOSSARY_KEY_BY_CANONICAL.get(canonical)
    if glossary_key and glossary_key in ANALYTE_GUIDE:
        return ANALYTE_GUIDE[glossary_key]["explanation"]
    return None


# ---------------------------------------------------------------------------


def parse_reference_range(raw: str) -> tuple[float, float] | None:
    """Parse a printed range such as '12.0 - 15.5' or '4.0 to 11.0'.

    Returns None when the text is not an unambiguous two-ended numeric range.
    """
    text = (raw or "").strip()
    if not text:
        return None
    text = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-")
    text = re.sub(r"\s+", " ", text)
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:-|to)\s*(-?\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if not match:
        return None
    low, high = float(match.group(1)), float(match.group(2))
    if low == high:
        return None
    return (min(low, high), max(low, high))


def _extraction_value(item: dict[str, Any]) -> str:
    corrected = (item.get("corrected_value_text") or "").strip()
    if corrected:
        return corrected
    return (item.get("value_text") or "").strip()


def _item_dto(item: dict[str, Any], plain: str | None = None) -> dict[str, Any]:
    return {
        "id": item["id"],
        "itemType": item["item_type"],
        "label": item.get("label") or "",
        "value": _extraction_value(item),
        "valueNumeric": item.get("value_numeric"),
        "unit": item.get("unit") or "",
        "referenceRange": item.get("reference_range") or "",
        "abnormalFlag": item.get("abnormal_flag") or "",
        "pageNumber": item.get("page_number"),
        "sourceText": item.get("source_text") or "",
        "extractionStatus": item.get("extraction_status") or "extracted",
        "verificationStatus": item.get("verification_status") or "unverified",
        "confidenceNote": item.get("confidence_note") or "",
        "plainExplanation": plain or "",
    }


def document_dates(pages: list[dict[str, Any]], extractions: list[dict[str, Any]]) -> list[str]:
    """Dates explicitly written in the document, normalised where possible."""
    found: list[str] = []
    for item in extractions:
        if item.get("item_type") != "document_date":
            continue
        raw = (item.get("value_text") or "").strip()
        iso_date = _normalise_date(raw)
        if iso_date:
            found.append(iso_date)
    if found:
        return sorted(set(found))
    for page in pages:
        for match in re.finditer(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", page.get("text_content") or ""):
            iso_date = _normalise_date(match.group(1))
            if iso_date:
                found.append(iso_date)
    return sorted(set(found))


def _normalise_date(raw: str) -> str | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if match:
        return raw
    match = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", raw)
    if not match:
        return None
    first, second, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if year < 100:
        year += 2000
    # Ambiguous day/month ordering is resolved only when one ordering is
    # impossible; otherwise the raw text is left unmodified.
    if first > 12 and second <= 12:
        day, month = first, second
    elif second > 12 and first <= 12:
        day, month = second, first
    else:
        day, month = first, second
    try:
        return f"{year:04d}-{month:02d}-{day:02d}"
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Prescription parsing
# ---------------------------------------------------------------------------

_STRENGTH_RE = re.compile(
    r"(?P<strength>\d+(?:\.\d+)?\s*(?:mg|mcg|\u00b5g|g|ml|iu|units?|%))(?![a-z])",
    re.IGNORECASE,
)
_FREQUENCY_MAP: list[tuple[str, str]] = [
    (r"\b1\s*-\s*0\s*-\s*1\b", "morning and evening (1-0-1)"),
    (r"\b0\s*-\s*0\s*-\s*1\b", "evening only (0-0-1)"),
    (r"\b1\s*-\s*0\s*-\s*0\b", "morning only (1-0-0)"),
    (r"\b1\s*-\s*1\s*-\s*1\b", "three times daily (1-1-1)"),
    (r"\bqid\b|\bqds\b|four\s*times", "four times daily"),
    (r"\btds\b|\btid\b|three\s*times|thrice", "three times daily"),
    (r"\bbd\b|\bbid\b|twice\s*(?:a|per)?\s*day|two\s*times", "twice daily"),
    (r"\bod\b|\bqd\b|once\s*(?:a|per)?\s*day|daily|every\s*day", "once daily"),
    (r"\bhs\b|at\s*bed\s*time|night", "at bedtime"),
    (r"\bsos\b|\bprn\b|as\s*needed|when\s*required", "only when needed"),
    (r"every\s*(\d+)\s*hours?", "at a stated interval in hours"),
]
_TIMING_RE = [
    (r"after\s*(?:food|meals?)|post\s*prandial|\bpc\b", "after food"),
    (r"before\s*(?:food|meals?)|empty\s*stomach|\bac\b", "before food"),
    (r"with\s*(?:food|meals?)|with\s*milk", "with food"),
    (r"bed\s*time|\bhs\b|at\s*night", "at bedtime"),
    (r"morning", "in the morning"),
]
_DURATION_RE = re.compile(
    r"(?:for|x|×)?\s*(?P<count>\d+)\s*(?P<unit>day|days|week|weeks|month|months)\b",
    re.IGNORECASE,
)
_PRESCRIBER_RE = re.compile(
    r"(?:Dr\.?|Doctor)[ \t]+([A-Z][A-Za-z.'\-]+(?:[ \t]+[A-Z][A-Za-z.'\-]+){0,3})"
)
_REG_NUMBER_RE = re.compile(
    r"(?:Reg(?:istration)?\.?\s*(?:No\.?|Number)?|NMC\s*No\.?|KMC\s*No\.?)\s*[:\-]?\s*([A-Z0-9\-/]{4,20})",
    re.IGNORECASE,
)


def _line_has_medication_signal(line: str) -> bool:
    if _STRENGTH_RE.search(line):
        return True
    return bool(re.search(r"\btab\.?\b|\bcap\.?\b|\btablet\b|\bcapsule\b|\binhaler\b|\bsyrup\b|\bdrops?\b", line, re.IGNORECASE))


NON_DRUG_PREFIX_WORDS = {
    "prescription",
    "rx",
    "adv",
    "take",
    "date",
    "patient",
    "name",
    "dr",
    "doctor",
    "clinic",
    "hospital",
    "signature",
    "age",
    "sex",
    "address",
    "diagnosis",
    "instructions",
}


def _medicine_name(line: str) -> str | None:
    strength = _STRENGTH_RE.search(line)
    prefix = line[: strength.start()] if strength else line
    prefix = re.sub(r"^\s*(?:\d+[.)]\s*|[-*\u2022]\s*)", "", prefix)
    prefix = re.sub(
        r"^\s*(?:tab\.?|tablet|cap\.?|capsule|inj\.?|injection|syp\.?|syrup|drops?|oint\.?|ointment)\s*",
        "",
        prefix,
        flags=re.IGNORECASE,
    )
    prefix = re.sub(r"\b(?:take|rx|adv)\b\s*", "", prefix, flags=re.IGNORECASE)
    words = [w for w in re.split(r"\s+", prefix.strip()) if w]
    if not words:
        return None
    name_words: list[str] = []
    for word in words[:6]:
        # Header words and dates appear before the medicine on single-line
        # prescriptions; they must never become part of the medicine name.
        if re.search(r"\d", word):
            continue
        if word.lower().strip(".,:") in NON_DRUG_PREFIX_WORDS:
            continue
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9\-+'/]{1,30}", word):
            name_words.append(word)
    if not name_words:
        return None
    return " ".join(name_words[-3:])


def parse_prescription(pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Structure the prescription text exactly as written.

    Every field records the source line and page. Fields that could not be read
    confidently are reported as unclear instead of being guessed.
    """
    medicines: list[dict[str, Any]] = []
    prescriber = {"name": None, "registrationNumber": None, "pageNumber": None, "sourceText": ""}
    unreadable_pages: list[dict[str, Any]] = []
    total_chars = 0

    for page in pages:
        text = page.get("text_content") or ""
        total_chars += len(text.strip())
        status = page.get("status") or "pending"
        if status in {"empty_or_unreadable", "error", "unavailable"}:
            unreadable_pages.append(
                {
                    "pageNumber": page.get("page_number"),
                    "status": status,
                    "detail": page.get("error") or "No readable text was recovered from this page.",
                }
            )
            continue
        if not prescriber["name"]:
            match = _PRESCRIBER_RE.search(text)
            if match:
                prescriber["name"] = match.group(0).strip()
                prescriber["pageNumber"] = page.get("page_number")
                prescriber["sourceText"] = _snippet(text, match.start(), match.end())
        if not prescriber["registrationNumber"]:
            match = _REG_NUMBER_RE.search(text)
            if match:
                prescriber["registrationNumber"] = match.group(1)
                prescriber["pageNumber"] = prescriber["pageNumber"] or page.get("page_number")
                prescriber["sourceText"] = prescriber["sourceText"] or _snippet(text, match.start(), match.end())

        for raw_line in re.split(r"[\n\r]+", text):
            line = raw_line.strip()
            if len(line) < 4 or len(line) > 300:
                continue
            if not _line_has_medication_signal(line):
                continue
            name = _medicine_name(line)
            if not name or len(name) < 3:
                continue
            if re.search(r"\breference|haemoglobin|hemoglobin|creatinine|glucose|sodium|potassium", name, re.IGNORECASE):
                continue
            strength_match = _STRENGTH_RE.search(line)
            frequency = _match_label(_FREQUENCY_MAP, line)
            timing = _match_label(_TIMING_RE, line)
            duration_match = _DURATION_RE.search(line)
            duration = f"{duration_match.group('count')} {duration_match.group('unit').lower()}" if duration_match else None

            dosage = strength_match.group("strength").strip() if strength_match else None
            missing = [field for field, value in (("dosage", dosage), ("frequency", frequency), ("duration", duration)) if not value]
            confidence = "clear" if not missing else ("unclear" if len(missing) < 3 else "unclear")
            medicines.append(
                {
                    "name": name,
                    "nameStatus": "clear" if len(name) > 2 else "unclear",
                    "dosage": dosage,
                    "frequency": frequency,
                    "timing": timing,
                    "duration": duration,
                    "instructions": line,
                    "clarificationNeeded": missing,
                    "confidence": confidence,
                    "pageNumber": page.get("page_number"),
                    "sourceText": line,
                    "verificationStatus": "unverified",
                    "plainExplanation": _medicine_plain(name, dosage, frequency, timing, duration),
                }
            )

    if not medicines:
        clarifications = [
            "No medicine entry could be reliably read. Review the original prescription image before relying on any instruction."
        ]
    else:
        clarifications = [
            f"{med['name']}: confirm {', '.join(med['clarificationNeeded'])} with the prescribing clinician."
            for med in medicines
            if med["clarificationNeeded"]
        ]

    return {
        "medicines": medicines,
        "medicineCount": len(medicines),
        "prescriber": prescriber,
        "prescriberStatus": "clear" if prescriber["name"] else "not_readable",
        "unreadablePages": unreadable_pages,
        "clarifications": clarifications,
        "readableCharacters": total_chars,
        "parseMode": "deterministic_pattern_parse",
        "safetyNote": (
            "Fields are transcribed exactly as written. CareTwin AI does not prescribe, adjust doses, "
            "or advise stopping any medicine. Confirm every instruction with the prescriber or pharmacist."
        ),
    }


def _match_label(patterns: list[tuple[str, str]], text: str) -> str | None:
    for pattern, label in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return label
    return None


def _medicine_plain(
    name: str,
    dosage: str | None,
    frequency: str | None,
    timing: str | None,
    duration: str | None,
) -> str:
    parts = [f"{name} is recorded on this prescription"]
    if dosage:
        parts.append(f"at a written strength of {dosage}")
    if frequency:
        parts.append(f"to be taken {frequency}")
    if timing:
        parts.append(timing)
    if duration:
        parts.append(f"for {duration}")
    if len(parts) == 1:
        return "The prescription records this medicine without a readable dose, frequency or duration."
    return ", ".join(parts) + ". This restates the written instruction; it is not advice to change anything."


# ---------------------------------------------------------------------------
# Document analysis
# ---------------------------------------------------------------------------


def analyze_document(
    *,
    document: dict[str, Any],
    pages: list[dict[str, Any]],
    extractions: list[dict[str, Any]],
    ai_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic analysis of one document.

    The output describes what the extractor found and where. It never asserts a
    diagnosis, a normal/abnormal conclusion independent of the report's own
    printed range, or any medication advice.
    """
    ai_status = ai_status or {"state": "not_configured", "configured": False, "model": ""}
    readings = [item for item in extractions if item.get("item_type") == "lab_finding"]
    med_lines = [item for item in extractions if item.get("item_type") == "medication_mention"]
    dates = document_dates(pages, extractions)
    used_ocr = any("ocr" in (page.get("extraction_method") or "").lower() for page in pages)

    values: list[dict[str, Any]] = []
    review_flags: list[dict[str, Any]] = []
    terminology: list[dict[str, str]] = []
    seen_terms: set[str] = set()

    for item in readings:
        canonical = canonical_analyte(item.get("label") or "")
        explanation = analyte_explanation(canonical) if canonical else None
        dto = _item_dto(item, explanation)
        dto["canonicalTest"] = canonical
        values.append(dto)
        if canonical and canonical not in seen_terms and explanation:
            seen_terms.add(canonical)
            terminology.append(
                {"term": analyte_display_name(canonical), "explanation": explanation, "basis": "matched test name"}
            )
        flag = _range_flag(item)
        if flag:
            review_flags.append(
                {
                    "label": item.get("label") or "",
                    "value": _extraction_value(item),
                    "unit": item.get("unit") or "",
                    "referenceRange": item.get("reference_range") or "",
                    "pageNumber": item.get("page_number"),
                    "reason": flag,
                    "verificationStatus": item.get("verification_status") or "unverified",
                    "sourceText": item.get("source_text") or "",
                }
            )
        if not (item.get("unit") or "").strip():
            review_flags.append(
                {
                    "label": item.get("label") or "",
                    "value": _extraction_value(item),
                    "unit": "",
                    "referenceRange": item.get("reference_range") or "",
                    "pageNumber": item.get("page_number"),
                    "reason": "No unit was printed or extracted for this value, so it cannot be interpreted or compared.",
                    "verificationStatus": item.get("verification_status") or "unverified",
                    "sourceText": item.get("source_text") or "",
                }
            )

    all_text = "\n".join((page.get("text_content") or "") for page in pages)
    for pattern, explanation in DOCUMENT_GLOSSARY:
        if re.search(pattern, all_text, re.IGNORECASE):
            term = re.search(pattern, all_text, re.IGNORECASE)
            label = (term.group(0) if term else pattern).strip()
            key = explanation.split(":")[0].lower()
            if key in seen_terms:
                continue
            seen_terms.add(key)
            terminology.append({"term": label, "explanation": explanation, "basis": "found in document text"})

    unreadable: list[dict[str, Any]] = []
    for page in pages:
        status = page.get("status") or "pending"
        if status in {"empty_or_unreadable", "error", "unavailable"}:
            unreadable.append(
                {
                    "scope": "page",
                    "pageNumber": page.get("page_number"),
                    "detail": page.get("error") or "No readable text could be recovered from this page.",
                }
            )
    if not readings and not med_lines:
        unreadable.append(
            {
                "scope": "document",
                "pageNumber": None,
                "detail": (
                    "Text was recovered but no structured clinical values or medicine instructions could be "
                    "identified by the deterministic extractor. The original document remains the source of truth."
                ),
            }
        )

    document_type = document.get("document_type") or "other_medical_document"
    verified = [item for item in extractions if item.get("verification_status") == "verified"]
    headline = f"{_type_label(document_type)} · {document.get('original_filename')}"
    summary_paragraph = _summary_paragraph(
        document=document,
        pages=pages,
        readings=len(readings),
        med_lines=len(med_lines),
        dates=dates,
        used_ocr=used_ocr,
        verified=len(verified),
    )

    key_information: list[dict[str, Any]] = []
    for dto in values[:20]:
        key_information.append({**dto, "kind": "value"})
    for item in med_lines[:10]:
        key_information.append({**(_item_dto(item)), "kind": "medication_text"})
    for item in extractions:
        if item.get("item_type") in {"diagnosis_text", "follow_up", "precaution", "discharge_instruction"}:
            key_information.append({**(_item_dto(item)), "kind": item["item_type"]})

    prescription = None
    if document_type == "prescription" or med_lines:
        prescription = parse_prescription(pages)
        for med in prescription["medicines"][:10]:
            if med["pageNumber"]:
                review_flags.append(
                    {
                        "label": f"Medicine instruction · {med['name']}",
                        "value": med["dosage"] or "(no dose read)",
                        "unit": "",
                        "referenceRange": "",
                        "pageNumber": med["pageNumber"],
                        "reason": (
                            "Prescription text is unverified. "
                            + (
                                f"Unclear: {', '.join(med['clarificationNeeded'])}."
                                if med["clarificationNeeded"]
                                else "Confirm the medicine, dose and timing with the prescriber."
                            )
                        ),
                        "verificationStatus": "unverified",
                        "sourceText": med["sourceText"],
                    }
                )

    questions = _questions(
        values=values,
        review_flags=review_flags,
        prescription=prescription,
        used_ocr=used_ocr,
        unreadable=unreadable,
        dates=dates,
    )

    return {
        "documentId": document["id"],
        "patientId": document["patient_id"],
        "documentType": document_type,
        "documentTypeLabel": _type_label(document_type),
        "generatedAt": iso(),
        "analysisMode": "deterministic_extraction_analysis",
        "aiUsed": False,
        "ai": {
            "state": ai_status.get("state", "not_configured"),
            "configured": bool(ai_status.get("configured")),
            "model": ai_status.get("model") or "",
            "message": (
                "This analysis was produced by the deterministic extractor and pattern parser. "
                "It is not a model-generated clinical interpretation."
            ),
        },
        "summary": {
            "headline": headline,
            "paragraph": summary_paragraph,
            "pageCount": len(pages),
            "extractionStatus": document.get("extraction_status") or "pending",
            "extractionMethod": document.get("extraction_method") or "",
            "extractionError": document.get("extraction_error") or "",
            "extractedItemCount": len(extractions),
            "verifiedItemCount": len(verified),
            "awaitingReviewCount": len(extractions) - len(verified),
            "usedOcr": used_ocr,
            "documentDates": dates,
            "uploadedAt": document.get("uploaded_at"),
            "processedAt": document.get("processed_at"),
        },
        "keyInformation": key_information[:40],
        "values": values,
        "terminology": terminology[:24],
        "findingsRequiringReview": review_flags[:40],
        "unreadableOrMissing": unreadable,
        "questionsToAsk": questions,
        "prescription": prescription,
        "limits": [
            "Extraction is mechanical: it can miss values, merge adjacent lines, or misread scanned text.",
            "Only reference ranges printed on this document are used; CareTwin AI does not supply reference ranges.",
            "Nothing here is a diagnosis, and no medicine dose or schedule is recommended.",
        ],
    }


def _range_flag(item: dict[str, Any]) -> str | None:
    low_high = parse_reference_range(item.get("reference_range") or "")
    value = item.get("value_numeric")
    if low_high is None or value is None:
        return None
    low, high = low_high
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if low <= numeric <= high:
        return None
    direction = "below" if numeric < low else "above"
    return (
        f"The extracted value is {direction} the reference range printed on this report "
        f"({item.get('reference_range')}). A clinician must interpret this in context; "
        "it is not a diagnosis."
    )


def _summary_paragraph(
    *,
    document: dict[str, Any],
    pages: list[dict[str, Any]],
    readings: int,
    med_lines: int,
    dates: list[str],
    used_ocr: bool,
    verified: int,
) -> str:
    readable = len([p for p in pages if (p.get("text_content") or "").strip()])
    parts = [
        f"{_type_label(document.get('document_type'))} with {len(pages)} page(s); "
        f"text was recovered from {readable} page(s) using "
        f"{document.get('extraction_method') or 'the configured extractor'}."
    ]
    if used_ocr:
        parts.append("At least one page was read with OCR, so character-level errors are possible and the original image should be checked.")
    parts.append(f"The deterministic extractor found {readings} value(s) and {med_lines} medicine or instruction line(s).")
    if dates:
        parts.append(f"Dates written in the document include {', '.join(dates[:3])}.")
    parts.append(f"{verified} extracted item(s) are clinician verified; the rest await review.")
    return " ".join(parts)


def _questions(
    *,
    values: list[dict[str, Any]],
    review_flags: list[dict[str, Any]],
    prescription: dict[str, Any] | None,
    used_ocr: bool,
    unreadable: list[dict[str, Any]],
    dates: list[str],
) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    for flag in review_flags[:6]:
        value_text = flag.get("value") or ""
        unit_text = flag.get("unit") or ""
        display = value_text
        if unit_text and unit_text.lower() not in value_text.lower():
            display = f"{value_text} {unit_text}".strip()
        if not unit_text and not flag.get("referenceRange"):
            questions.append(
                {
                    "question": f"What unit applies to {flag['label']} = {value_text} on my report?",
                    "basis": f"Printed on page {flag.get('pageNumber') or '?'} without a unit.",
                }
            )
        elif flag.get("referenceRange"):
            questions.append(
                {
                    "question": f"What does {flag['label']} = {display} mean for me, given the report's range of {flag['referenceRange']}?",
                    "basis": f"Value outside the printed range on page {flag.get('pageNumber') or '?'}.",
                }
            )
    if prescription and prescription.get("clarifications"):
        questions.append(
            {
                "question": "Can we confirm the medicine name, dose and timing that are unclear on this prescription?",
                "basis": "; ".join(prescription["clarifications"][:3]),
            }
        )
    if used_ocr:
        questions.append(
            {
                "question": "Can you check the numbers on this scanned report against the original image?",
                "basis": "OCR was used, so digits may be misread.",
            }
        )
    if any(v.get("verificationStatus") != "verified" for v in values):
        questions.append(
            {
                "question": "Which of these extracted values has the care team reviewed and confirmed?",
                "basis": "Extracted items are unverified until a clinician reviews them.",
            }
        )
    if unreadable and not values:
        questions.append(
            {
                "question": "Can you show me which parts of this document were unreadable?",
                "basis": "No structured values were extracted from this document.",
            }
        )
    if dates:
        questions.append(
            {
                "question": "Which date on this report should be used for my records?",
                "basis": f"Multiple dates were written in the document ({', '.join(dates[:3])}).",
            }
        )
    if not questions:
        questions.append(
            {
                "question": "Can you explain how this document relates to my care plan?",
                "basis": "No value-level concerns were detected by the deterministic extractor.",
            }
        )
    return questions[:10]


def _type_label(document_type: str | None) -> str:
    labels = {
        "blood_test_report": "Blood test report",
        "prescription": "Prescription",
        "mri_ct_report": "MRI / CT report",
        "xray_report": "X-ray report",
        "ultrasound_report": "Ultrasound report",
        "discharge_summary": "Discharge summary",
        "consultation_report": "Consultation note",
        "medical_history": "Previous medical record",
        "follow_up_report": "Follow-up report",
        "medical_report_image": "Scanned medical image report",
        "pdf_report": "Medical report",
        "other_medical_document": "Medical document",
    }
    return labels.get(document_type or "", "Medical document")


def _snippet(text: str, start: int, end: int, window: int = 70) -> str:
    snippet = text[max(0, start - window) : min(len(text), end + window)]
    return re.sub(r"\s+", " ", snippet).strip()[:400]


# ---------------------------------------------------------------------------
# Report comparison
# ---------------------------------------------------------------------------


def _comparison_row(canonical: str, unit: str, previous: dict[str, Any], latest: dict[str, Any]) -> dict[str, Any]:
    difference = latest["value"] - previous["value"]
    validity_reasons: list[str] = []
    if previous["date"] == latest["date"]:
        validity_reasons.append("Both readings share the same date, so a time-ordered change cannot be established.")
    if previous["documentId"] == latest["documentId"]:
        validity_reasons.append("Both readings come from the same document.")
    if previous["dateSource"] != "document" or latest["dateSource"] != "document":
        validity_reasons.append(
            "At least one date is the upload date because no date was written in that document; "
            "the time order may not reflect when the sample was taken."
        )
    if previous["value"] == latest["value"]:
        validity_reasons.append("Values are identical.")
    return {
        "canonicalTest": canonical,
        "label": analyte_display_name(canonical),
        "explanation": analyte_explanation(canonical),
        "unit": unit,
        "unitRaw": latest["unitRaw"],
        "comparable": not validity_reasons,
        "validityReasons": validity_reasons,
        "previous": previous,
        "latest": latest,
        "difference": round(difference, 6),
        "differencePercent": round((difference / previous["value"]) * 100, 2) if previous["value"] else None,
        "direction": "increased" if difference > 0 else "decreased" if difference < 0 else "unchanged",
        "verification": {
            "previous": previous["verificationStatus"],
            "latest": latest["verificationStatus"],
            "bothVerified": previous["verificationStatus"] == "verified" and latest["verificationStatus"] == "verified",
        },
        "interpretationNote": (
            "The difference is arithmetic only. CareTwin AI does not judge whether a change is good or bad, "
            "and a change is not a diagnosis."
        ),
    }


def compare_reports(
    *,
    documents: list[dict[str, Any]],
    extractions_by_document: dict[str, list[dict[str, Any]]],
    pages_by_document: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Compare compatible lab readings across documents.

    Compatibility requires the same canonical analyte *and* the same normalised
    unit. Anything else is reported as not comparable with the reason stated.
    """
    observations: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for doc in documents:
        if doc.get("is_duplicate_of"):
            continue
        doc_id = doc["id"]
        dates = document_dates(pages_by_document.get(doc_id, []), extractions_by_document.get(doc_id, []))
        observed = dates[0] if dates else (doc.get("uploaded_at") or "")[:10]
        for item in extractions_by_document.get(doc_id, []):
            if item.get("item_type") != "lab_finding":
                continue
            canonical = canonical_analyte(item.get("label") or "")
            unit = _norm_unit(item.get("unit") or "")
            numeric = item.get("value_numeric")
            if not canonical:
                skipped.append(
                    {
                        "documentId": doc_id,
                        "label": item.get("label") or "",
                        "reason": "Test name not recognised, so it cannot be matched to another report.",
                    }
                )
                continue
            if numeric is None:
                skipped.append(
                    {
                        "documentId": doc_id,
                        "label": item.get("label") or "",
                        "reason": "No numeric value was extracted, so no change can be calculated.",
                    }
                )
                continue
            if not unit:
                skipped.append(
                    {
                        "documentId": doc_id,
                        "label": item.get("label") or "",
                        "reason": "No unit was extracted; comparing without a unit would be unsafe.",
                    }
                )
                continue
            observations.append(
                {
                    "documentId": doc_id,
                    "documentName": doc.get("original_filename"),
                    "documentType": doc.get("document_type"),
                    "date": observed,
                    "dateSource": "document" if dates else "upload",
                    "canonical": canonical,
                    "unit": unit,
                    "unitRaw": item.get("unit") or "",
                    "label": item.get("label") or "",
                    "value": float(numeric),
                    "valueText": _extraction_value(item),
                    "referenceRange": item.get("reference_range") or "",
                    "pageNumber": item.get("page_number"),
                    "verificationStatus": item.get("verification_status") or "unverified",
                    "extractionId": item["id"],
                }
            )

    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for obs in observations:
        groups.setdefault((obs["canonical"], obs["unit"]), []).append(obs)

    comparisons: list[dict[str, Any]] = []
    insufficient: list[dict[str, Any]] = []
    for (canonical, unit), rows in groups.items():
        # One reading per document: two lines in the same report are not a history.
        per_document: dict[str, dict[str, Any]] = {}
        for row in sorted(rows, key=lambda r: r["date"]):
            per_document[row["documentId"]] = row
        # One reading per collection date: repeated copies of the same report are
        # the same measurement, not a second time point.
        per_date: dict[str, dict[str, Any]] = {}
        for row in sorted(per_document.values(), key=lambda r: r["date"]):
            per_date[row["date"]] = row
        distinct = list(per_date.values())
        if len(distinct) < 2:
            insufficient.append(
                {
                    "canonicalTest": canonical,
                    "label": analyte_display_name(canonical),
                    "unit": unit,
                    "reason": "Only one document records this test with this unit.",
                }
            )
            continue
        dated = [row for row in distinct if row["dateSource"] == "document"]
        # Prefer two documents that state their own date: an upload timestamp is
        # not evidence of when the sample was taken.
        pool = dated if len(dated) >= 2 else distinct
        ordered = sorted(pool, key=lambda r: (r["date"], r["documentId"]))
        pairs = list(zip(ordered, ordered[1:]))[:8]
        for previous, latest in pairs:
            comparisons.append(_comparison_row(canonical, unit, previous, latest))
    comparisons.sort(key=lambda c: (c["label"], c["latest"]["date"]), reverse=False)

    # Group units that were seen for a canonical test but could not be compared.
    unit_mismatches: list[dict[str, Any]] = []
    by_canonical: dict[str, set[str]] = {}
    for obs in observations:
        by_canonical.setdefault(obs["canonical"], set()).add(obs["unit"])
    for canonical, units in by_canonical.items():
        if len(units) > 1:
            unit_mismatches.append(
                {
                    "canonicalTest": canonical,
                    "label": analyte_display_name(canonical),
                    "units": sorted(units),
                    "reason": "Reports state this test in different units, so no comparison is offered.",
                }
            )

    return {
        "generatedAt": iso(),
        "documentCount": len(documents),
        "observationCount": len(observations),
        "comparisons": comparisons,
        "insufficientHistory": insufficient[:20],
        "notComparable": skipped[:50],
        "unitMismatches": unit_mismatches,
        "notes": [
            "Only the same test with the same unit from two different documents is compared.",
            "Documents that state their own date are preferred over the upload timestamp.",
            "Fasting and non-fasting glucose are treated as different tests.",
            "Values that were not clinician verified are labelled as unverified in every comparison.",
        ],
    }
