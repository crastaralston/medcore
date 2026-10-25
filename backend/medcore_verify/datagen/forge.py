"""Two families of forgery, applied to copies of genuine claims.

F2 "clean edit": the forger changes facts on one document and the document is re-printed
perfectly, as an AI editor would. No pixel or file traces remain, so only the
cross-document and medical checks can catch it.

F5 "PDF overlay edit": the forger paints a white box over a value inside the PDF and
types a new value on top, then saves the file again. The original text stays underneath.
"""

from __future__ import annotations

import os
import random
import tempfile
from dataclasses import dataclass
from datetime import timedelta

import pymupdf

from .render import fmt_date, render_claim
from .scenarios import Claim, Item, Test, indian

EDIT_TOOLS = ["iLovePDF", "Sejda PDF Editor", "PDFescape Online", "Smallpdf"]


@dataclass
class Forgery:
    forgery_type: str  # "F2" or "F5"
    variant: str
    document: str  # file name of the changed document
    description: str


F2_VARIANTS = ("lab_value", "room_days", "bill_dates", "total_only", "lab_after_discharge",
               "diagnosis_upgrade", "pharmacy_qty")
F5_VARIANTS = ("overlay_total", "overlay_lab_value", "overlay_report_date")


def quoted_test(claim: Claim) -> str:
    """The lab value the discharge summary quotes, which a forger most wants to change."""
    return {"dengue": "Platelet Count", "typhoid": "Widal Test (S. Typhi O)",
            "appendicitis": "Total WBC Count"}[claim.diagnosis_key]


def _forged_value(claim: Claim, original: str, rng: random.Random) -> str:
    if claim.diagnosis_key == "dengue":  # make the platelet drop look severe
        return indian(rng.randrange(18_000, 42_000, 1000))
    if claim.diagnosis_key == "typhoid":
        return "1:640" if original != "1:640" else "1:1280"
    return indian(rng.randrange(19_000, 24_000, 100))  # appendicitis: inflate WBC


def apply_f2(claim: Claim, variant: str, rng: random.Random) -> Forgery:
    """Changes `claim` in place. Returns what changed."""
    if variant == "lab_value":
        name = quoted_test(claim)
        tests = [Test(t.name, t.value, t.unit, t.ref) for t in claim.lab_reports[0].tests]
        for t in tests:
            if t.name == name:
                old, t.value = t.value, _forged_value(claim, t.value, rng)
                break
        claim.overrides["lab_report_1"] = {"tests": tests}
        return Forgery("F2", variant, "lab_report_1.pdf", f"{name} changed from {old} to {t.value}")

    if variant == "room_days":
        extra = rng.randint(2, 3)
        for it in claim.bill_items:
            if it.description.startswith(("Room Rent", "Nursing")):
                it.qty += extra
        return Forgery("F2", variant, "hospital_bill.pdf",
                       f"Room rent and nursing billed for {extra} extra days; total updated to match")

    if variant == "bill_dates":
        extra = rng.randint(2, 3)
        claim.bill_admission = claim.admission - timedelta(days=extra)
        for it in claim.bill_items:
            if it.description.startswith(("Room Rent", "Nursing")):
                it.qty += extra
        return Forgery("F2", variant, "hospital_bill.pdf",
                       f"Admission date on the bill moved {extra} days earlier, with matching room days")

    if variant == "total_only":
        bump = float(rng.randrange(5000, 15001, 500))
        claim.bill_total_override = claim.bill_total + bump
        return Forgery("F2", variant, "hospital_bill.pdf", f"Grand total raised by Rs. {indian(bump)}")

    if variant == "lab_after_discharge":
        report = claim.lab_reports[0]
        shifted = claim.discharge + timedelta(days=rng.randint(2, 6))
        claim.overrides["lab_report_1"] = {"collected": shifted, "reported": shifted}
        return Forgery("F2", variant, "lab_report_1.pdf",
                       f"Lab report re-dated from {fmt_date(report.reported, 0)} to {fmt_date(shifted, 0)}")

    if variant == "diagnosis_upgrade":
        upgraded = "Dengue fever with thrombocytopenia"
        claim.overrides["discharge_summary"] = {"diagnosis": upgraded}
        claim.bill_diagnosis = upgraded
        return Forgery("F2", variant, "discharge_summary.pdf",
                       f"Diagnosis changed from '{claim.diagnosis_text}' to '{upgraded}' on summary and bill")

    if variant == "pharmacy_qty":
        items = [Item(i.description, i.qty * 3, i.rate) for i in claim.pharmacy_items]
        claim.overrides["pharmacy_bill"] = {"items": items}
        return Forgery("F2", variant, "pharmacy_bill.pdf",
                       "Every pharmacy quantity tripled, with a matching total (not expected to be caught yet)")

    raise ValueError(f"unknown F2 variant {variant!r}")


def _overlay(pdf: bytes, old: str, new: str, rng: random.Random, pick: str = "last",
             within: str | None = None, right_align: bool = False) -> bytes:
    """Paint a white box over `old` and type `new` on top, then save incrementally."""
    fd, path = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(pdf)
        doc = pymupdf.open(path)
        page = doc[0]
        hits = page.search_for(old)
        if within:
            area = page.search_for(within)
            hits = [h for h in hits if any(h.intersects(a) for a in area)]
        if not hits:
            raise ValueError(f"text {old!r} not found")
        rect = hits[-1] if pick == "last" else hits[0]
        page.draw_rect(rect + (-1, -1, 1, 1), color=None, fill=(1, 1, 1), overlay=True)
        size = round(rect.height * 0.78, 1)
        width = pymupdf.get_text_length(new, fontname="helv", fontsize=size)
        x = rect.x1 - width if right_align else rect.x0
        page.insert_text((x, rect.y1 - rect.height * 0.22), new, fontsize=size, fontname="helv")
        meta = dict(doc.metadata)
        meta["modDate"] = pymupdf.get_pdf_now()
        if rng.random() < 0.5:
            meta["producer"] = rng.choice(EDIT_TOOLS)
        doc.set_metadata(meta)
        doc.save(path, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
        doc.close()
        with open(path, "rb") as f:
            return f.read()
    finally:
        os.unlink(path)


def apply_f5(claim: Claim, files: dict[str, bytes], variant: str, rng: random.Random) -> Forgery:
    """Edits rendered PDF bytes in `files` in place. Returns what changed."""
    if variant == "overlay_total":
        old = indian(claim.bill_total, 2)
        new = indian(claim.bill_total + rng.randrange(8000, 20001, 500), 2)
        files["hospital_bill.pdf"] = _overlay(files["hospital_bill.pdf"], old, new, rng, right_align=True)
        return Forgery("F5", variant, "hospital_bill.pdf", f"Grand total painted over: {old} -> {new}")

    if variant == "overlay_lab_value":
        name = quoted_test(claim)
        test = next(t for t in claim.lab_reports[0].tests if t.name == name)
        new = _forged_value(claim, test.value, rng)
        files["lab_report_1.pdf"] = _overlay(files["lab_report_1.pdf"], test.value, new, rng, pick="first")
        return Forgery("F5", variant, "lab_report_1.pdf", f"{name} painted over: {test.value} -> {new}")

    if variant == "overlay_report_date":
        report = claim.lab_reports[0]
        style = claim.style
        old = fmt_date(report.reported, style)
        new = fmt_date(claim.discharge + timedelta(days=rng.randint(2, 5)), style)
        files["lab_report_1.pdf"] = _overlay(files["lab_report_1.pdf"], old, new, rng,
                                             within=f"Reported On: {old}")
        return Forgery("F5", variant, "lab_report_1.pdf", f"Report date painted over: {old} -> {new}")

    raise ValueError(f"unknown F5 variant {variant!r}")


def forge(claim: Claim, forgery_type: str, variant: str, seed: int) -> tuple[dict[str, bytes], Forgery]:
    """Render `claim` with one forgery applied. `claim` is not modified."""
    rng = random.Random(seed)
    c = claim.clone(claim.claim_id)
    if forgery_type == "F2":
        forgery = apply_f2(c, variant, rng)
        return render_claim(c), forgery
    if forgery_type == "F5":
        files = render_claim(c)
        forgery = apply_f5(c, files, variant, rng)
        return files, forgery
    raise ValueError(f"unknown forgery type {forgery_type!r}")
