"""Data structures shared by the reader, the three checkers and the report."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Literal

from PIL import Image

DocType = Literal[
    "discharge_summary", "hospital_bill", "lab_report", "pharmacy_bill", "prescription", "unknown"
]
Severity = Literal["high", "medium", "low"]

DOC_TYPE_LABELS: dict[str, str] = {
    "discharge_summary": "Discharge summary",
    "hospital_bill": "Hospital bill",
    "lab_report": "Lab report",
    "pharmacy_bill": "Pharmacy bill",
    "prescription": "Prescription",
    "unknown": "Unrecognised document",
}


@dataclass
class SourceFile:
    """A file exactly as uploaded, plus the text lines the reader recovered from it."""

    name: str
    kind: Literal["pdf", "image"]
    data: bytes
    lines: list[str] = field(default_factory=list)
    preview: Image.Image | None = None
    # Words printed on top of other words: a sign that something was pasted over.
    overlapping_text: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@dataclass
class LabTest:
    name: str  # canonical name from the knowledge table, e.g. "platelet count"
    raw_name: str
    value: str
    number: float | None
    unit: str
    line: str


@dataclass
class LineItem:
    description: str
    qty: float | None
    rate: float | None
    amount: float | None
    line: str


@dataclass
class ExtractedDoc:
    """Fields read from one document. Every field keeps the source line as evidence."""

    file_name: str
    doc_type: DocType
    patient_name: str | None = None
    age: int | None = None
    sex: str | None = None
    hospital: str | None = None
    lab_name: str | None = None
    doctor: str | None = None
    doctor_reg: str | None = None
    admission: date | None = None
    discharge: date | None = None
    collected: date | None = None  # lab sample collection date
    doc_date: date | None = None  # bill date, lab reporting date or invoice date
    diagnosis: str | None = None
    procedure: str | None = None
    tests: list[LabTest] = field(default_factory=list)
    items: list[LineItem] = field(default_factory=list)
    total: float | None = None
    medicines: list[str] = field(default_factory=list)
    # Lab values a discharge summary quotes, as printed: {"platelet count": ["79,000", "1,42,000"]}
    quoted_values: dict[str, list[str]] = field(default_factory=dict)
    evidence: dict[str, str] = field(default_factory=dict)
    seal: dict[str, Any] | None = None  # the QR seal check, when the claim check looked for one

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        for key in ("admission", "discharge", "collected", "doc_date"):
            if d[key] is not None:
                d[key] = d[key].isoformat()
        d["doc_type_label"] = DOC_TYPE_LABELS[self.doc_type]
        return d


@dataclass
class Flag:
    checker: Literal[1, 2, 3]
    code: str
    severity: Severity
    title: str
    detail: str
    documents: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


CHECKER_NAMES = {1: "Editing signs", 2: "Documents agree?", 3: "Medicine fits?"}


@dataclass
class Report:
    verdict: Literal["hold", "pass_with_notes", "pass"]
    flags: list[Flag]
    documents: list[ExtractedDoc]
    seconds: float
    notes: list[str] = field(default_factory=list)  # what could not be checked, and why

    @property
    def verdict_label(self) -> str:
        return {
            "hold": "Hold for review",
            "pass_with_notes": "Pass, with notes",
            "pass": "Pass",
        }[self.verdict]

    def to_json(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "verdict_label": self.verdict_label,
            "flags": [asdict(f) | {"checker_name": CHECKER_NAMES[f.checker]} for f in self.flags],
            "documents": [d.to_json() for d in self.documents],
            "notes": self.notes,
            "seconds": round(self.seconds, 2),
        }


def decide_verdict(flags: list[Flag]) -> Literal["hold", "pass_with_notes", "pass"]:
    """Hold if any high flag, or two or more medium flags; notes for anything else."""
    highs = sum(f.severity == "high" for f in flags)
    mediums = sum(f.severity == "medium" for f in flags)
    if highs or mediums >= 2:
        return "hold"
    if flags:
        return "pass_with_notes"
    return "pass"
