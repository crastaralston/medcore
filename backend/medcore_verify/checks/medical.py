"""Checker 3: does the medicine in the claim make sense?

Rules live in knowledge.json. This version covers three diagnoses: dengue, typhoid and
acute appendicitis. Claims for anything else get a note, not a flag.
"""

from __future__ import annotations

import re

from . import knowledge
from ..models import ExtractedDoc, Flag, LabTest


def _diagnosis_key(text: str | None) -> str | None:
    if not text:
        return None
    t = text.lower()
    for key, spec in knowledge()["diagnoses"].items():
        if any(a in t for a in spec["aliases"]):
            return key
    return None


def _result(test: LabTest) -> str:
    """'positive', 'negative' or 'unclear' for qualitative and titre tests."""
    spec = knowledge()["tests"].get(test.name, {})
    v = test.value.lower()
    if spec.get("kind") == "titre":
        m = re.search(r"1\s*:\s*(\d+)", v)
        if not m:
            return "unclear"
        return "positive" if int(m.group(1)) >= spec.get("positive_from", 160) else "negative"
    if any(w in v for w in knowledge()["negative_words"]):
        return "negative"
    if any(w in v for w in knowledge()["positive_words"]):
        return "positive"
    return "unclear"


def _test_label(name: str) -> str:
    return knowledge()["tests"][name]["label"]


def check(docs: list[ExtractedDoc]) -> tuple[list[Flag], list[str]]:
    flags: list[Flag] = []
    summary = next((d for d in docs if d.doc_type == "discharge_summary"), None)
    bill = next((d for d in docs if d.doc_type == "hospital_bill"), None)
    labs = [d for d in docs if d.doc_type == "lab_report"]
    tests = [t for lab in labs for t in lab.tests]
    lab_files = [lab.file_name for lab in labs]

    # Physically impossible values are wrong whatever the diagnosis.
    for lab in labs:
        for t in lab.tests:
            spec = knowledge()["tests"].get(t.name, {})
            lo_hi = spec.get("plausible")
            if t.number is not None and lo_hi and not (lo_hi[0] <= t.number <= lo_hi[1]):
                flags.append(Flag(3, "impossible_value", "high", "Lab value outside the possible range",
                                  f"{t.raw_name} of {t.value} {t.unit} is outside what a living patient "
                                  f"can have ({lo_hi[0]:,} to {lo_hi[1]:,}).", [lab.file_name], [t.line]))

    diagnosis = (summary and summary.diagnosis) or (bill and bill.diagnosis)
    key = _diagnosis_key(diagnosis)
    if diagnosis is None:
        return flags, ["No diagnosis found, so the medical checks were skipped."]
    if key is None:
        covered = ", ".join(s["label"] for s in knowledge()["diagnoses"].values())
        return flags, [f"No medical rules yet for '{diagnosis}'. Covered so far: {covered}."]
    rule = knowledge()["diagnoses"][key]
    source = summary or bill
    dx_files = [source.file_name]

    # 1. A confirming test must be present and positive.
    confirm = [t for t in tests if t.name in rule["confirm_any"]]
    options = ", ".join(_test_label(n) for n in rule["confirm_any"])
    if not confirm:
        flags.append(Flag(3, "confirm_test_missing", "medium", "No test in the file confirms the diagnosis",
                          f"A diagnosis of {rule['label'].lower()} is normally backed by one of: {options}. "
                          "None of the lab reports has one.", dx_files + lab_files,
                          [source.evidence.get("diagnosis", diagnosis)]))
    elif all(_result(t) == "negative" for t in confirm):
        flags.append(Flag(3, "confirm_test_negative", "high", "The confirming test is negative",
                          f"The claim says {rule['label'].lower()}, but every confirming test is negative.",
                          dx_files + lab_files, [t.line for t in confirm]))

    # 2. "Thrombocytopenia" means low platelets; the lab reports must show it.
    platelet = rule.get("thrombocytopenia_test")
    if platelet and "thrombocytopenia" in diagnosis.lower():
        counts = [t for t in tests if t.name == platelet and t.number is not None]
        low = knowledge()["tests"][platelet]["normal"][0]
        if counts and min(t.number for t in counts) >= low:
            flags.append(Flag(3, "thrombocytopenia_not_shown", "high",
                              "Diagnosis says low platelets, but every count is normal",
                              f"Thrombocytopenia means a platelet count below {low:,}/cumm. "
                              f"The lowest count in the file is {min(t.number for t in counts):,.0f}/cumm.",
                              dx_files + lab_files, [t.line for t in counts]))
        elif not counts:
            flags.append(Flag(3, "thrombocytopenia_no_count", "medium", "Low platelets claimed with no platelet count",
                              "The diagnosis says thrombocytopenia, but no lab report has a platelet count.",
                              dx_files, [source.evidence.get("diagnosis", diagnosis)]))

    stay = None
    admission = (summary and summary.admission) or (bill and bill.admission)
    discharge = (summary and summary.discharge) or (bill and bill.discharge)
    if admission and discharge:
        stay = (discharge - admission).days

    # 3. Some conditions need repeated tests during a stay (platelets in dengue).
    repeat = rule.get("repeat_test")
    if repeat and stay is not None and stay >= repeat["if_stay_at_least"]:
        n = sum(t.name == repeat["test"] for t in tests)
        if 0 < n < repeat["min_count"]:
            flags.append(Flag(3, "single_reading", "medium", "Only one reading where repeats are expected",
                              f"A {stay}-day stay for {rule['label'].lower()} normally has repeated "
                              f"{_test_label(repeat['test']).lower()}s; the file has {n}.", lab_files, []))

    # 4. Length of stay.
    lo, hi = rule["stay_days"]
    if stay is not None and stay > hi:
        flags.append(Flag(3, "long_stay", "medium", "Stay is longer than usual for this diagnosis",
                          f"{stay} days for {rule['label'].lower()}; usual is {lo} to {hi} days.", dx_files, []))
    elif stay is not None and stay < lo:
        flags.append(Flag(3, "short_stay", "low", "Stay is shorter than usual for this diagnosis",
                          f"{stay} days for {rule['label'].lower()}; usual is {lo} to {hi} days.", dx_files, []))

    # 5. Drugs that should be avoided for this condition.
    meds = [(m, d.file_name) for d in docs if d.doc_type in ("discharge_summary", "pharmacy_bill") for m in d.medicines]
    for word in rule.get("avoid_drugs", []):
        hits = [(m, f) for m, f in meds if word in m.lower()]
        if hits:
            flags.append(Flag(3, "avoided_drug", "medium", "A drug usually avoided for this condition",
                              f"{hits[0][0]} is usually avoided in {rule['label'].lower()}.",
                              sorted({f for _, f in hits}), [m for m, _ in hits]))

    # 6. Surgery charges must match a recorded procedure, and the other way round.
    surgical_items = [i for i in (bill.items if bill else [])
                      if any(w in i.description.lower() for w in knowledge()["surgical_bill_items"])]
    procedure = summary.procedure if summary else None
    if surgical_items and not rule["surgical"] and not procedure:
        flags.append(Flag(3, "surgery_billed_not_done", "high", "Surgery charges billed, but no surgery recorded",
                          f"The bill charges for {', '.join(i.description for i in surgical_items)}, "
                          f"but {rule['label'].lower()} is treated without surgery and no procedure is recorded.",
                          [bill.file_name] + dx_files, [i.line for i in surgical_items]))
    if rule["surgical"] and procedure and bill and not surgical_items:
        flags.append(Flag(3, "surgery_not_billed", "medium", "Surgery recorded, but no theatre or surgeon charges",
                          f"The summary records '{procedure}', but the bill has no operation theatre, "
                          "surgeon or anaesthesia charges.", dx_files + [bill.file_name], []))
    words = rule.get("procedure_words")
    if words and procedure and not any(w in procedure.lower() for w in words):
        flags.append(Flag(3, "unexpected_procedure", "low", "Procedure does not match the diagnosis",
                          f"'{procedure}' is not a usual procedure for {rule['label'].lower()}.", dx_files, []))
    return flags, []
