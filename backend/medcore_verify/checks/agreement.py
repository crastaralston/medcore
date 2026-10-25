"""Checker 2: do the documents in one claim agree with each other?

The discharge summary is the reference; when it is missing, the hospital bill is.
"""

from __future__ import annotations

import re
from datetime import timedelta

from rapidfuzz import fuzz

from . import knowledge
from ..models import DOC_TYPE_LABELS, ExtractedDoc, Flag

ROOM_ITEMS = re.compile(r"room rent|bed charges|ward charges|room charges|nursing", re.I)
NAME_TITLES = re.compile(r"^(mr|mrs|ms|miss|shri|smt|master|baby|dr)\.?\s+", re.I)


def _label(doc: ExtractedDoc) -> str:
    return f"{DOC_TYPE_LABELS[doc.doc_type]} ({doc.file_name})"


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z ]", "", NAME_TITLES.sub("", name.strip()).lower())


def _norm_value(value: str) -> str:
    return value.replace(",", "").replace(" ", "").lower()


def _money(n: float) -> str:
    return f"Rs. {n:,.2f}"


def _first(docs: list[ExtractedDoc], doc_type: str) -> ExtractedDoc | None:
    return next((d for d in docs if d.doc_type == doc_type), None)


def _identity(docs: list[ExtractedDoc], ref: ExtractedDoc) -> list[Flag]:
    flags = []
    for d in docs:
        if d is ref:
            continue
        if d.patient_name and ref.patient_name:
            score = fuzz.token_sort_ratio(_norm_name(d.patient_name), _norm_name(ref.patient_name))
            if score < 85:
                flags.append(Flag(2, "name_mismatch", "high", "Patient name differs between documents",
                                  f"'{d.patient_name}' on the {DOC_TYPE_LABELS[d.doc_type].lower()}, "
                                  f"'{ref.patient_name}' on the {DOC_TYPE_LABELS[ref.doc_type].lower()}.",
                                  [d.file_name, ref.file_name],
                                  [d.evidence.get("patient_name", ""), ref.evidence.get("patient_name", "")]))
        if d.age is not None and ref.age is not None and abs(d.age - ref.age) > 1:
            flags.append(Flag(2, "age_mismatch", "high", "Patient age differs between documents",
                              f"Age {d.age} on the {DOC_TYPE_LABELS[d.doc_type].lower()}, "
                              f"{ref.age} on the {DOC_TYPE_LABELS[ref.doc_type].lower()}.",
                              [d.file_name, ref.file_name], [d.evidence.get("age", ""), ref.evidence.get("age", "")]))
        if d.sex and ref.sex and d.sex != ref.sex:
            flags.append(Flag(2, "sex_mismatch", "high", "Patient sex differs between documents",
                              f"{d.sex} on the {DOC_TYPE_LABELS[d.doc_type].lower()}, "
                              f"{ref.sex} on the {DOC_TYPE_LABELS[ref.doc_type].lower()}.",
                              [d.file_name, ref.file_name], [d.evidence.get("sex", ""), ref.evidence.get("sex", "")]))
    return flags


def _dates(docs: list[ExtractedDoc], summary: ExtractedDoc | None, bill: ExtractedDoc | None,
           admission, discharge) -> list[Flag]:
    flags = []
    if summary and bill:
        for attr, word in (("admission", "Admission"), ("discharge", "Discharge")):
            a, b = getattr(summary, attr), getattr(bill, attr)
            if a and b and a != b:
                flags.append(Flag(2, f"{attr}_date_mismatch", "high", f"{word} date differs between summary and bill",
                                  f"{a:%d %b %Y} on the discharge summary, {b:%d %b %Y} on the hospital bill.",
                                  [summary.file_name, bill.file_name],
                                  [summary.evidence.get(attr, ""), bill.evidence.get(attr, "")]))
    if not (admission and discharge):
        return flags
    for d in docs:
        if d.doc_type == "lab_report":
            when = d.doc_date or d.collected
            if when and when > discharge:
                flags.append(Flag(2, "lab_after_discharge", "high", "Lab report dated after discharge",
                                  f"Reported {when:%d %b %Y}, but the patient was discharged on {discharge:%d %b %Y}.",
                                  [d.file_name], [d.evidence.get("doc_date", "")]))
            elif when and when < admission - timedelta(days=30):
                flags.append(Flag(2, "lab_long_before", "medium", "Lab report dated long before admission",
                                  f"Reported {when:%d %b %Y}, more than 30 days before admission on {admission:%d %b %Y}.",
                                  [d.file_name], [d.evidence.get("doc_date", "")]))
            if d.collected and d.doc_date and d.doc_date < d.collected:
                flags.append(Flag(2, "lab_reported_before_collected", "medium",
                                  "Lab report issued before the sample was collected",
                                  f"Collected {d.collected:%d %b %Y}, reported {d.doc_date:%d %b %Y}.",
                                  [d.file_name], [d.evidence.get("collected", ""), d.evidence.get("doc_date", "")]))
        if d.doc_type == "pharmacy_bill" and d.doc_date and not (
                admission - timedelta(days=3) <= d.doc_date <= discharge + timedelta(days=3)):
            flags.append(Flag(2, "pharmacy_date_outside_stay", "medium", "Pharmacy bill dated outside the stay",
                              f"Invoice dated {d.doc_date:%d %b %Y}; stay was {admission:%d %b} to {discharge:%d %b %Y}.",
                              [d.file_name], [d.evidence.get("doc_date", "")]))
    return flags


def _arithmetic(d: ExtractedDoc) -> list[Flag]:
    flags = []
    for item in d.items:
        if item.qty is not None and item.rate is not None and item.amount is not None:
            if abs(item.qty * item.rate - item.amount) > 1:
                flags.append(Flag(2, "line_math", "medium", "A bill line does not multiply out",
                                  f"{item.description}: {item.qty:g} x {_money(item.rate)} is "
                                  f"{_money(item.qty * item.rate)}, but the line says {_money(item.amount)}.",
                                  [d.file_name], [item.line]))
    if d.items and d.total is not None:
        summed = round(sum(i.amount or 0 for i in d.items), 2)
        if abs(summed - d.total) > max(1.0, d.total * 0.001):
            flags.append(Flag(2, "total_mismatch", "high", f"{DOC_TYPE_LABELS[d.doc_type]} total does not add up",
                              f"The lines add up to {_money(summed)}, but the total says {_money(d.total)} "
                              f"(difference {_money(d.total - summed)}).",
                              [d.file_name], [d.evidence.get("total", "")]))
    return flags


def _room_days(bill: ExtractedDoc, admission, discharge) -> list[Flag]:
    stay = (discharge - admission).days
    flags = []
    for item in bill.items:
        if ROOM_ITEMS.search(item.description) and item.qty is not None and item.qty > stay + 1:
            flags.append(Flag(2, "room_days_exceed_stay", "high", "More days billed than the patient stayed",
                              f"{item.description} billed for {item.qty:g} days; the stay was {stay} days "
                              f"({admission:%d %b} to {discharge:%d %b %Y}).",
                              [bill.file_name], [item.line]))
    return flags


def _quoted_values(summary: ExtractedDoc, labs: list[ExtractedDoc]) -> list[Flag]:
    flags = []
    for test, quoted in summary.quoted_values.items():
        label = knowledge()["tests"][test]["label"]
        found = [(lab, t) for lab in labs for t in lab.tests if t.name == test]
        shown = {_norm_value(t.value) for _, t in found}
        if not found:
            flags.append(Flag(2, "quoted_test_missing", "medium", "Summary quotes a test no lab report shows",
                              f"The discharge summary quotes {label.lower()} ({', '.join(quoted)}), "
                              "but none of the lab reports contains it.",
                              [summary.file_name], quoted))
            continue
        for value in quoted:
            if _norm_value(value) not in shown:
                in_labs = "; ".join(f"{t.value} in {lab.file_name}" for lab, t in found)
                flags.append(Flag(2, "quoted_value_mismatch", "high", "Lab value differs from the discharge summary",
                                  f"The discharge summary quotes {label.lower()} as {value}, "
                                  f"but the lab reports show {in_labs}.",
                                  [summary.file_name, *sorted({lab.file_name for lab, _ in found})],
                                  [t.line for _, t in found]))
    return flags


def check(docs: list[ExtractedDoc]) -> tuple[list[Flag], list[str]]:
    notes: list[str] = []
    summary = _first(docs, "discharge_summary")
    bill = _first(docs, "hospital_bill")
    labs = [d for d in docs if d.doc_type == "lab_report"]
    ref = summary or bill
    if ref is None:
        return [], ["No discharge summary or hospital bill, so the documents could not be cross-checked."]
    if summary is None:
        notes.append("No discharge summary: dates and lab values were checked against the bill only.")

    admission = (summary and summary.admission) or (bill and bill.admission)
    discharge = (summary and summary.discharge) or (bill and bill.discharge)

    flags = _identity(docs, ref)
    flags += _dates(docs, summary, bill, admission, discharge)
    for d in docs:
        if d.doc_type in ("hospital_bill", "pharmacy_bill"):
            flags += _arithmetic(d)
    if bill and admission and discharge:
        flags += _room_days(bill, admission, discharge)
    if summary and labs:
        flags += _quoted_values(summary, labs)
    if summary and bill and summary.hospital and bill.hospital:
        if fuzz.token_sort_ratio(summary.hospital.lower(), bill.hospital.lower()) < 85:
            flags.append(Flag(2, "hospital_mismatch", "high", "Hospital name differs between summary and bill",
                              f"'{summary.hospital}' on the summary, '{bill.hospital}' on the bill.",
                              [summary.file_name, bill.file_name], [summary.hospital, bill.hospital]))
    if summary and bill and summary.diagnosis and bill.diagnosis:
        if fuzz.token_set_ratio(summary.diagnosis.lower(), bill.diagnosis.lower()) < 70:
            flags.append(Flag(2, "diagnosis_mismatch", "medium", "Diagnosis differs between summary and bill",
                              f"'{summary.diagnosis}' on the summary, '{bill.diagnosis}' on the bill.",
                              [summary.file_name, bill.file_name],
                              [summary.evidence.get("diagnosis", ""), bill.evidence.get("diagnosis", "")]))
    regs: dict[str, tuple[str, str]] = {}
    for d in docs:
        if d.doctor and d.doctor_reg:
            key = _norm_name(d.doctor)
            if key in regs and regs[key][0] != d.doctor_reg:
                flags.append(Flag(2, "doctor_reg_mismatch", "high", "Same doctor, different registration number",
                                  f"{d.doctor}: {regs[key][0]} in {regs[key][1]}, {d.doctor_reg} in {d.file_name}.",
                                  [regs[key][1], d.file_name], [d.evidence.get("doctor_reg", "")]))
            regs.setdefault(key, (d.doctor_reg, d.file_name))
    if not labs:
        notes.append("No lab reports in this claim.")
    return flags, notes
