"""Which facts a seal signs for each document type, and how a page is compared with them."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from ..checks import knowledge
from ..models import ExtractedDoc

COMMON = ("patient_name", "age", "sex")
BY_TYPE = {
    "discharge_summary": ("admission", "discharge", "diagnosis", "procedure"),
    "hospital_bill": ("admission", "discharge", "doc_date", "total"),
    "lab_report": ("collected", "doc_date", "tests"),
    "pharmacy_bill": ("doc_date", "total"),
}
LABELS = {
    "patient_name": "Patient name", "age": "Age", "sex": "Sex", "admission": "Admission date",
    "discharge": "Discharge date", "diagnosis": "Diagnosis", "procedure": "Procedure",
    "collected": "Sample collected", "total": "Total amount",
}
DATE_LABELS = {"hospital_bill": "Bill date", "lab_report": "Reported on", "pharmacy_bill": "Invoice date"}
SEAL_CAPTION = re.compile(r"MedCore Seal\s+[A-Z0-9]{4}(?:-[A-Z0-9]{4})*|Scan to verify")


@dataclass
class FieldCheck:
    field: str
    label: str
    signed: str
    printed: str | None
    status: str  # "match", "different" or "unreadable"


def facts(doc: ExtractedDoc) -> dict[str, Any]:
    """The facts a seal signs, read from the document the hospital is about to issue."""
    out: dict[str, Any] = {}
    for name in COMMON + BY_TYPE.get(doc.doc_type, ()):
        if name == "tests":
            if doc.tests:
                out["tests"] = {t.name: t.value for t in doc.tests}
            continue
        value = getattr(doc, name)
        if value is None or value == "":
            continue
        out[name] = value.isoformat() if isinstance(value, date) else value
    return out


def _label(name: str, doc_type: str) -> str:
    if name == "doc_date":
        return DATE_LABELS.get(doc_type, "Document date")
    return LABELS.get(name, name)


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().casefold().replace(",", "")


def _show(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def compare(signed: dict[str, Any], doc: ExtractedDoc) -> list[FieldCheck]:
    """Every signed fact against what the page shows now."""
    printed = facts(doc)
    checks: list[FieldCheck] = []
    for name, value in signed.items():
        if name == "tests":
            now = printed.get("tests", {})
            for test, signed_value in value.items():
                label = knowledge()["tests"].get(test, {}).get("label", test)
                shown = now.get(test)
                status = "unreadable" if shown is None else ("match" if _norm(shown) == _norm(signed_value)
                                                             else "different")
                checks.append(FieldCheck(f"tests.{test}", label, str(signed_value), shown, status))
            continue
        shown = printed.get(name)
        if shown is None:
            status = "unreadable"
        elif isinstance(value, (int, float)) and isinstance(shown, (int, float)):
            status = "match" if abs(float(value) - float(shown)) < 0.005 else "different"
        else:
            status = "match" if _norm(shown) == _norm(value) else "different"
        checks.append(FieldCheck(name, _label(name, doc.doc_type), _show(value),
                                 None if shown is None else _show(shown), status))
    return checks


def text_fingerprint(lines: list[str]) -> str:
    """A hash of the whole printed text, ignoring the seal's own caption. Any change to
    any word on the page changes it. Used for PDFs, where the text is read exactly."""
    cleaned = []
    for line in lines:
        line = re.sub(r"\s+", " ", SEAL_CAPTION.sub(" ", line)).strip()
        if line:
            cleaned.append(line)
    return hashlib.sha256("\n".join(cleaned).encode()).hexdigest()[:32]
