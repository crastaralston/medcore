"""Prints a Claim onto four kinds of PDF documents, in two layout styles.

Each document is built from a 'view' of the claim, so a forgery can override one
document's fields (say, the lab report's patient age) without touching the others.
"""

from __future__ import annotations

import io
import zlib
from datetime import date
from typing import Any

from reportlab.lib.colors import Color, black
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from .scenarios import Claim, Item, LabReport, indian

WIDTH, HEIGHT = A4
MARGIN = 48
FOOTER = "SYNTHETIC SAMPLE FOR TESTING MEDCORE VERIFY - NOT A REAL MEDICAL RECORD"
GREY = Color(0.45, 0.45, 0.45)
HEADER_FILL = Color(0.88, 0.9, 0.93)

FONTS = [("Helvetica", "Helvetica-Bold"), ("Times-Roman", "Times-Bold")]
CREATORS = ["MediSoft HMS 4.2", "eHospital Suite 2.1"]


def fmt_date(d: date, style: int) -> str:
    return d.strftime("%d/%m/%Y") if style == 0 else d.strftime("%d-%b-%Y")


def sex_text(sex: str, style: int) -> str:
    return sex if style == 0 else sex[0]


class Page:
    """A thin wrapper over a ReportLab canvas that writes top-down lines."""

    def __init__(self, canvas: Canvas, style: int):
        self.c = canvas
        self.style = style
        self.font, self.bold = FONTS[style]
        self.y = HEIGHT - MARGIN

    def text(self, s: str, size: float = 10, bold: bool = False, x: float = MARGIN, gap: float = 15) -> None:
        self.c.setFont(self.bold if bold else self.font, size)
        self.c.drawString(x, self.y, s)
        self.y -= gap

    def centred(self, s: str, size: float = 12, bold: bool = True, gap: float = 20) -> None:
        self.c.setFont(self.bold if bold else self.font, size)
        self.c.drawCentredString(WIDTH / 2, self.y, s)
        self.y -= gap

    def rule(self, gap: float = 14) -> None:
        self.c.setLineWidth(0.6)
        self.c.line(MARGIN, self.y + 8, WIDTH - MARGIN, self.y + 8)
        self.y -= gap

    def pair(self, left: str, right: str, gap: float = 15) -> None:
        self.c.setFont(self.font, 10)
        self.c.drawString(MARGIN, self.y, left)
        self.c.drawString(WIDTH / 2 + 20, self.y, right)
        self.y -= gap

    def paragraph(self, s: str, size: float = 10, indent: float = 0) -> None:
        self.c.setFont(self.font, size)
        max_w = WIDTH - 2 * MARGIN - indent
        line = ""
        for word in s.split():
            trial = f"{line} {word}".strip()
            if stringWidth(trial, self.font, size) > max_w:
                self.c.drawString(MARGIN + indent, self.y, line)
                self.y -= size + 4
                line = word
            else:
                line = trial
        if line:
            self.c.drawString(MARGIN + indent, self.y, line)
            self.y -= size + 4
        self.y -= 4

    def table(self, header: list[str], rows: list[list[str]], cols: list[float], right_from: int) -> None:
        """Columns at x offsets `cols`; columns from index `right_from` are right-aligned."""
        self.c.setFillColor(HEADER_FILL)
        self.c.rect(MARGIN, self.y - 5, WIDTH - 2 * MARGIN, 17, stroke=0, fill=1)
        self.c.setFillColor(black)
        self._row(header, cols, right_from, bold=True)
        for r in rows:
            self._row(r, cols, right_from)
        self.y -= 4

    def _row(self, cells: list[str], cols: list[float], right_from: int, bold: bool = False) -> None:
        self.c.setFont(self.bold if bold else self.font, 9.5)
        for i, (cell, x) in enumerate(zip(cells, cols)):
            if i >= right_from:
                self.c.drawRightString(MARGIN + x, self.y, cell)
            else:
                self.c.drawString(MARGIN + x, self.y, cell)
        self.y -= 16

    def header(self, name: str, address: str) -> None:
        self.text(name, size=16, bold=True, gap=16)
        self.text(address, size=9, gap=12)
        self.text(f"Phone: 022-{25000000 + zlib.crc32(name.encode()) % 9999999:08d}", size=9, gap=16)
        self.rule()

    def footer(self) -> None:
        self.c.setFont("Helvetica", 7)
        self.c.setFillColor(GREY)
        self.c.drawCentredString(WIDTH / 2, 24, FOOTER)
        self.c.setFillColor(black)


def _new_pdf(claim: Claim, title: str) -> tuple[io.BytesIO, Canvas]:
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=A4)
    c.setTitle(title)
    c.setCreator(CREATORS[claim.style])
    c.setAuthor(claim.hospital[0])
    return buf, c


def _finish(buf: io.BytesIO, c: Canvas, page: Page) -> bytes:
    page.footer()
    c.showPage()
    c.save()
    return buf.getvalue()


def view(claim: Claim, key: str) -> dict[str, Any]:
    """The facts one document prints, after any forgery overrides for that document."""
    v: dict[str, Any] = {
        "patient_name": claim.patient_name, "age": claim.age, "sex": claim.sex,
        "admission": claim.admission, "discharge": claim.discharge,
        "diagnosis": claim.diagnosis_text, "doctor": claim.doctor, "doctor_reg": claim.doctor_reg,
    }
    v.update(claim.overrides.get(key, {}))
    return v


def discharge_summary(claim: Claim) -> bytes:
    v = view(claim, "discharge_summary")
    s = claim.style
    buf, c = _new_pdf(claim, "Discharge Summary")
    p = Page(c, s)
    p.header(*claim.hospital)
    p.centred("DISCHARGE SUMMARY")
    if s == 0:
        p.pair(f"Patient Name: {v['patient_name']}", f"Age/Sex: {v['age']} Y / {sex_text(v['sex'], s)}")
        p.pair(f"Date of Admission: {fmt_date(v['admission'], s)}",
               f"Date of Discharge: {fmt_date(v['discharge'], s)}")
        p.text(f"Consultant: {v['doctor']}, {claim.doctor_qual}")
        p.text(f"Reg. No.: {v['doctor_reg']}")
        p.text(f"Final Diagnosis: {v['diagnosis']}", bold=True)
        if claim.procedure:
            p.text(f"Procedure: {claim.procedure}")
    else:
        p.pair(f"Name of Patient : {v['patient_name']}",
               f"Age / Gender : {v['age']} Years / {sex_text(v['sex'], s)}")
        p.pair(f"DOA : {fmt_date(v['admission'], s)}", f"DOD : {fmt_date(v['discharge'], s)}")
        p.text(f"Treating Doctor : {v['doctor']}, {claim.doctor_qual}")
        p.text(f"Regn. No. : {v['doctor_reg']}")
        p.text(f"Diagnosis : {v['diagnosis']}", bold=True)
        if claim.procedure:
            p.text(f"Surgery Performed : {claim.procedure}")
    p.y -= 6
    for heading, body in (("Chief Complaints:", claim.complaints),
                          ("Investigations:", v.get("investigations", claim.investigations_summary)),
                          ("Course in Hospital:", claim.course)):
        p.text(heading, bold=True, gap=14)
        p.paragraph(body)
    p.text("Treatment Given:", bold=True, gap=14)
    for t in claim.treatment:
        p.text(f"- {t}", gap=14)
    p.y -= 4
    p.text("Condition at Discharge: Stable", gap=28)
    p.text(v["doctor"], bold=True, gap=14)
    p.text(f"{claim.doctor_qual} | Reg. No. {v['doctor_reg']}", size=9)
    return _finish(buf, c, p)


def hospital_bill(claim: Claim) -> bytes:
    v = view(claim, "hospital_bill")
    s = claim.style
    buf, c = _new_pdf(claim, "Final Bill")
    p = Page(c, s)
    p.header(*claim.hospital)
    p.centred("FINAL IN-PATIENT BILL" if s == 0 else "IPD FINAL BILL")
    admission = claim.bill_admission or v["admission"]
    p.pair(f"Bill No.: {claim.bill_no}", f"Bill Date: {fmt_date(v['discharge'], s)}")
    if s == 0:
        p.pair(f"Patient Name: {v['patient_name']}", f"Age/Sex: {v['age']} Y / {sex_text(v['sex'], s)}")
        p.pair(f"Date of Admission: {fmt_date(admission, s)}",
               f"Date of Discharge: {fmt_date(v['discharge'], s)}")
    else:
        p.pair(f"Name of Patient : {v['patient_name']}",
               f"Age / Gender : {v['age']} Years / {sex_text(v['sex'], s)}")
        p.pair(f"DOA : {fmt_date(admission, s)}", f"DOD : {fmt_date(v['discharge'], s)}")
    p.text(f"Diagnosis: {claim.bill_diagnosis or v['diagnosis']}")
    p.text(f"Consultant: {v['doctor']}", gap=22)
    rows = [[str(i), it.description, str(it.qty), indian(it.rate, 2), indian(it.amount, 2)]
            for i, it in enumerate(claim.bill_items, 1)]
    p.table(["S.No", "Particulars", "Qty", "Rate (Rs.)", "Amount (Rs.)"], rows,
            cols=[0, 34, 330, 410, 499], right_from=2)
    p.rule(gap=6)
    label = "Grand Total (Rs.)" if s == 0 else "Net Payable Amount (Rs.)"
    p.c.setFont(p.bold, 10.5)
    p.c.drawString(MARGIN + 34, p.y, label)
    p.c.drawRightString(MARGIN + 499, p.y, indian(claim.bill_total, 2))
    p.y -= 40
    p.text("Authorised Signatory", size=9)
    return _finish(buf, c, p)


def lab_report(claim: Claim, report: LabReport, index: int) -> bytes:
    v = view(claim, f"lab_report_{index}")
    s = claim.style
    buf, c = _new_pdf(claim, "Laboratory Report")
    p = Page(c, s)
    p.header(*claim.lab)
    p.centred(report.title)
    collected = v.get("collected", report.collected)
    reported = v.get("reported", report.reported)
    p.pair(f"Patient Name: {v['patient_name']}", f"Age/Sex: {v['age']} Y / {sex_text(v['sex'], s)}")
    p.pair(f"Referred By: {v['doctor']}", f"Report No.: {report.report_no}")
    p.pair(f"Sample Collected On: {fmt_date(collected, s)}", f"Reported On: {fmt_date(reported, s)}", gap=22)
    tests = v.get("tests", report.tests)
    rows = [[t.name, t.value, t.unit, t.ref] for t in tests]
    p.table(["Test", "Result", "Unit", "Reference Range"], rows, cols=[0, 190, 300, 370], right_from=99)
    p.y -= 10
    p.centred("--- End of Report ---", size=9, bold=False, gap=40)
    p.text(claim.pathologist, bold=True, gap=14)
    p.text("MD (Pathology), Consultant Pathologist", size=9)
    return _finish(buf, c, p)


def pharmacy_bill(claim: Claim) -> bytes:
    v = view(claim, "pharmacy_bill")
    s = claim.style
    buf, c = _new_pdf(claim, "Pharmacy Invoice")
    p = Page(c, s)
    p.header(*claim.pharmacy)
    p.centred("TAX INVOICE" if s == 0 else "CASH MEMO")
    p.pair(f"Invoice No.: {claim.pharmacy_invoice}",
           f"Invoice Date: {fmt_date(v.get('date', claim.pharmacy_date), s)}")
    p.pair(f"Patient Name: {v['patient_name']}", f"Prescribed By: {v['doctor']}", gap=22)
    items: list[Item] = v.get("items", claim.pharmacy_items)
    rows = [[str(i), it.description, str(it.qty), indian(it.rate, 2), indian(it.amount, 2)]
            for i, it in enumerate(items, 1)]
    p.table(["S.No", "Product", "Qty", "Rate (Rs.)", "Amount (Rs.)"], rows,
            cols=[0, 34, 330, 410, 499], right_from=2)
    p.rule(gap=6)
    total = v.get("total", round(sum(i.amount for i in items), 2))
    p.c.setFont(p.bold, 10.5)
    p.c.drawString(MARGIN + 34, p.y, "Total (Rs.)")
    p.c.drawRightString(MARGIN + 499, p.y, indian(total, 2))
    p.y -= 40
    p.text("Registered Pharmacist", size=9)
    return _finish(buf, c, p)


def render_claim(claim: Claim) -> dict[str, bytes]:
    """All documents of a claim as {file name: PDF bytes}."""
    files = {
        "discharge_summary.pdf": discharge_summary(claim),
        "hospital_bill.pdf": hospital_bill(claim),
        "pharmacy_bill.pdf": pharmacy_bill(claim),
    }
    for i, report in enumerate(claim.lab_reports, 1):
        files[f"lab_report_{i}.pdf"] = lab_report(claim, report, i)
    return files
