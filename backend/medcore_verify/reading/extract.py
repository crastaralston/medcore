"""Recognises the document type and pulls out the fields the checkers compare.

The parsers look for common Indian labels ('DOA', 'Date of Admission', 'Age / Gender')
rather than fixed positions, so they also cope with layouts they were not written for.
Every field keeps the line it came from, which the report shows as evidence.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from ..checks import knowledge
from ..models import DocType, ExtractedDoc, LabTest, LineItem, SourceFile

COLUMN = re.compile(r"\s{2,}")
NUMBER = re.compile(r"^-?\d[\d,]*(?:\.\d+)?$")
DATE_TOKEN = re.compile(
    r"\b(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{1,2}[\- ](?:[A-Za-z]{3,9})[\- ,]+\d{2,4}|\d{4}-\d{2}-\d{2})\b"
)
DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d-%b-%Y", "%d %b %Y",
                "%d-%B-%Y", "%d %B %Y", "%d %b, %Y", "%d %B, %Y", "%Y-%m-%d")

TYPE_KEYWORDS: dict[DocType, list[str]] = {
    "discharge_summary": ["discharge summary", "course in hospital", "condition at discharge", "chief complaints"],
    "hospital_bill": ["final bill", "in-patient bill", "ipd final bill", "bill no", "room rent", "grand total",
                      "net payable"],
    "lab_report": ["reference range", "sample collected", "reported on", "pathologist", "laboratory",
                   "haematology", "radiology report", "microbiology"],
    "pharmacy_bill": ["tax invoice", "cash memo", "pharmacy", "chemist", "medical & general", "pharmacist",
                      "invoice no"],
    "prescription": ["prescription", "rx", "sig:"],
}

HEADER_WORDS: dict[str, tuple[str, ...]] = {
    "hospital": ("hospital", "nursing home", "clinic", "medical centre", "medical center", "healthcare"),
    "lab": ("laborator", "diagnostic", "path lab", "pathology", "imaging", "scan centre"),
    "pharmacy": ("pharmacy", "chemist", "medical & general", "medical stores", "medicals", "drug house"),
}


def parse_number(text: str) -> float | None:
    t = text.strip().replace(" ", "")
    t = t.removeprefix("Rs.").removeprefix("Rs").removeprefix("₹")
    if not NUMBER.match(t):
        return None
    return float(t.replace(",", ""))


def parse_date(text: str) -> date | None:
    m = DATE_TOKEN.search(text)
    if not m:
        return None
    token = re.sub(r"\s+", " ", m.group(1)).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(token, fmt).date()
        except ValueError:
            continue
    return None


def _label_value(lines: list[str], labels: list[str]) -> tuple[str, str] | None:
    """Find 'Label: value' on any line. Returns (value, line). Labels are tried in order."""
    for label in labels:
        pattern = re.compile(rf"(?:^|\s{{2,}}|\b){re.escape(label)}\s*[:\-]\s*(.+?)(?:\s{{2,}}|$)", re.I)
        for line in lines:
            m = pattern.search(line)
            if m and m.group(1).strip():
                return m.group(1).strip(), line
    return None


def classify(lines: list[str]) -> DocType:
    head = "\n".join(lines[:12]).lower()
    body = "\n".join(lines).lower()
    scores: dict[DocType, int] = {}
    for doc_type, words in TYPE_KEYWORDS.items():
        score = sum(2 if w in head else 1 for w in words if w in body)
        if score:
            scores[doc_type] = score
    if not scores:
        return "unknown"
    return max(scores, key=lambda k: scores[k])


def _header_name(lines: list[str], kind: str) -> str | None:
    for line in lines[:4]:
        if any(w in line.lower() for w in HEADER_WORDS[kind]):
            return line.strip()
    return lines[0].strip() if lines else None


def _person_fields(doc: ExtractedDoc, lines: list[str]) -> None:
    found = _label_value(lines, ["Patient Name", "Name of Patient", "Name of the Patient", "Patient"])
    if found:
        doc.patient_name = re.sub(r"^(mr|mrs|ms|miss|shri|smt|master|baby)\.?\s+", "", found[0], flags=re.I)
        doc.evidence["patient_name"] = found[1]
    for line in lines:
        m = re.search(r"age\s*/\s*(?:sex|gender)\s*[:\-]\s*(\d{1,3})\s*(?:y|yrs?|years?)?\s*/\s*(male|female|m|f)\b",
                      line, re.I)
        if not m:
            m = re.search(r"\bage\s*[:\-]\s*(\d{1,3}).{0,30}?\b(?:sex|gender)\s*[:\-]\s*(male|female|m|f)\b", line, re.I)
        if m:
            doc.age = int(m.group(1))
            doc.sex = "Male" if m.group(2).lower().startswith("m") else "Female"
            doc.evidence["age"] = doc.evidence["sex"] = line
            break


def _doctor_fields(doc: ExtractedDoc, lines: list[str], labels: list[str]) -> None:
    found = _label_value(lines, labels)
    if found:
        doc.doctor = found[0].split(",")[0].strip()
        doc.evidence["doctor"] = found[1]
    reg = _label_value(lines, ["Reg. No.", "Regn. No.", "Reg No", "Registration No", "Reg. No"])
    if reg:
        doc.doctor_reg = reg[0].split()[0]
        doc.evidence["doctor_reg"] = reg[1]


def _date_field(doc: ExtractedDoc, lines: list[str], attr: str, labels: list[str]) -> None:
    found = _label_value(lines, labels)
    if found:
        d = parse_date(found[0])
        if d:
            setattr(doc, attr, d)
            doc.evidence[attr] = found[1]


def _stay_dates(doc: ExtractedDoc, lines: list[str]) -> None:
    _date_field(doc, lines, "admission", ["Date of Admission", "DOA", "Admission Date", "Admitted On"])
    _date_field(doc, lines, "discharge", ["Date of Discharge", "DOD", "Discharge Date", "Discharged On"])


def _test_aliases() -> list[tuple[str, str]]:
    pairs = [(alias, canon) for canon, spec in knowledge()["tests"].items() for alias in spec["aliases"]]
    return sorted(pairs, key=lambda p: -len(p[0]))  # longest alias first


def _read_tests(lines: list[str]) -> list[LabTest]:
    tests = []
    for line in lines:
        cells = COLUMN.split(line.strip())
        if len(cells) < 2:
            continue
        name = cells[0].lower()
        for alias, canon in _test_aliases():
            if name == alias or name.startswith(alias + " ") or name.startswith(alias + "("):
                value = cells[1].strip()
                unit = cells[2].strip() if len(cells) > 3 else ""
                tests.append(LabTest(canon, cells[0], value, parse_number(value), unit, line))
                break
    return tests


def _quoted_values(lines: list[str]) -> dict[str, list[str]]:
    """Lab values that a discharge summary quotes in its Investigations paragraph.

    'Platelet count 79,000/cumm on 03/05/2026; 1,42,000/cumm on 07/05/2026.' gives
    {"platelet count": ["79,000", "1,42,000"]}. Dates are removed first so their digits
    are not mistaken for values; a sentence end stops the search.
    """
    text = " ".join(lines)
    m = re.search(r"investigations?\s*:(.+?)(?:course in hospital|treatment given|condition at discharge|$)",
                  text, re.I)
    if not m:
        return {}
    section = DATE_TOKEN.sub(" ", m.group(1))
    found: dict[str, list[str]] = {}
    for canon, spec in knowledge()["tests"].items():
        if not spec.get("quotable"):
            continue
        for alias in sorted(spec["aliases"], key=len, reverse=True):
            hit = re.search(re.escape(alias), section, re.I)
            if not hit:
                continue
            rest = section[hit.end():]
            stop = re.search(r"\.\s+[A-Z]|\.\s*$", rest)
            segment = rest[: stop.start()] if stop else rest
            if spec["kind"] == "titre":
                first = re.search(r"1\s*:\s*\d+", segment)
                values = [first.group(0).replace(" ", "")] if first else []
            else:
                values = re.findall(r"\d[\d,]*(?:\.\d+)?", segment)
            if values:
                found[canon] = values
            break
    return found


def _read_items(lines: list[str]) -> list[LineItem]:
    items = []
    for line in lines:
        cells = COLUMN.split(line.strip())
        if len(cells) < 4:
            continue
        qty, rate, amount = (parse_number(c) for c in cells[-3:])
        if qty is None or rate is None or amount is None:
            continue
        desc_cells = cells[:-3]
        if desc_cells and re.fullmatch(r"\d{1,3}\.?", desc_cells[0]):
            desc_cells = desc_cells[1:]
        desc = " ".join(desc_cells).strip()
        if desc:
            items.append(LineItem(desc, qty, rate, amount, line))
    return items


def _read_total(lines: list[str]) -> tuple[float, str] | None:
    pattern = re.compile(r"grand total|net payable|total amount|net amount|^total\b|bill amount", re.I)
    for line in reversed(lines):
        cells = COLUMN.split(line.strip())
        if pattern.search(cells[0]):
            for cell in reversed(cells[1:]):
                n = parse_number(cell)
                if n is not None:
                    return n, line
    return None


def extract(src: SourceFile) -> ExtractedDoc:
    lines = [ln for ln in src.lines if ln.strip()]
    doc = ExtractedDoc(file_name=src.name, doc_type=classify(lines))
    _person_fields(doc, lines)

    if doc.doc_type == "discharge_summary":
        doc.hospital = _header_name(lines, "hospital")
        _stay_dates(doc, lines)
        _doctor_fields(doc, lines, ["Consultant", "Treating Doctor", "Treating Consultant", "Attending Doctor"])
        found = _label_value(lines, ["Final Diagnosis", "Diagnosis", "Provisional Diagnosis"])
        if found:
            doc.diagnosis, doc.evidence["diagnosis"] = found
        found = _label_value(lines, ["Procedure", "Surgery Performed", "Procedure Done", "Operation"])
        if found:
            doc.procedure, doc.evidence["procedure"] = found
        doc.quoted_values = _quoted_values(lines)
        doc.medicines = [ln.lstrip("-• ").strip() for ln in lines
                         if re.match(r"^\s*[-•]?\s*(tab|inj|cap|syp|syr)\.?\s", ln, re.I)]
    elif doc.doc_type == "hospital_bill":
        doc.hospital = _header_name(lines, "hospital")
        _stay_dates(doc, lines)
        _date_field(doc, lines, "doc_date", ["Bill Date", "Date"])
        _doctor_fields(doc, lines, ["Consultant", "Treating Doctor"])
        found = _label_value(lines, ["Diagnosis"])
        if found:
            doc.diagnosis, doc.evidence["diagnosis"] = found
        doc.items = _read_items(lines)
        total = _read_total(lines)
        if total:
            doc.total, doc.evidence["total"] = total
    elif doc.doc_type == "lab_report":
        doc.lab_name = _header_name(lines, "lab")
        _date_field(doc, lines, "doc_date", ["Reported On", "Report Date", "Reporting Date"])
        _date_field(doc, lines, "collected", ["Sample Collected On", "Collected On", "Collection Date"])
        _doctor_fields(doc, lines, ["Referred By", "Ref. By", "Ref By"])
        doc.tests = _read_tests(lines)
    elif doc.doc_type == "pharmacy_bill":
        doc.hospital = _header_name(lines, "pharmacy")
        _date_field(doc, lines, "doc_date", ["Invoice Date", "Bill Date", "Date"])
        _doctor_fields(doc, lines, ["Prescribed By", "Doctor", "Dr. Name"])
        doc.items = _read_items(lines)
        doc.medicines = [i.description for i in doc.items]
        total = _read_total(lines)
        if total:
            doc.total, doc.evidence["total"] = total
    return doc
