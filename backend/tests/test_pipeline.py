import shutil
from datetime import date

import pymupdf
import pytest

from medcore_verify.datagen.forge import F2_VARIANTS, F5_VARIANTS, forge
from medcore_verify.datagen.render import render_claim
from medcore_verify.datagen.scenarios import DIAGNOSES, indian, make_claim
from medcore_verify.pipeline import InvalidClaim, analyze
from medcore_verify.reading.extract import parse_date, parse_number


def run(files: dict[str, bytes]):
    report, _ = analyze(list(files.items()))
    return report


def test_indian_number_format():
    assert indian(132000) == "1,32,000"
    assert indian(12500, 2) == "12,500.00"
    assert indian(999) == "999"
    assert indian(2.999, 2) == "3.00"
    assert parse_number("1,32,000") == 132000
    assert parse_number("Rs. 12,500.00") == 12500
    assert parse_number("1:160") is None


@pytest.mark.parametrize("text,expected", [
    ("03/05/2026", date(2026, 5, 3)),
    ("03-May-2026", date(2026, 5, 3)),
    ("3 May 2026", date(2026, 5, 3)),
    ("2026-05-03", date(2026, 5, 3)),
    ("Reported On: 07.05.2026", date(2026, 5, 7)),
    ("no date here", None),
])
def test_parse_date(text, expected):
    assert parse_date(text) == expected


@pytest.mark.parametrize("diagnosis", DIAGNOSES)
@pytest.mark.parametrize("seed", range(8))
def test_genuine_claims_raise_no_flags(diagnosis, seed):
    report = run(render_claim(make_claim("G", diagnosis, 1000 + seed)))
    assert report.flags == [], [f.title for f in report.flags]
    assert report.verdict == "pass"
    assert {d.doc_type for d in report.documents} == {"discharge_summary", "hospital_bill", "lab_report",
                                                      "pharmacy_bill"}


DETECTABLE_F2 = [v for v in F2_VARIANTS if v != "pharmacy_qty"]


@pytest.mark.parametrize("variant", DETECTABLE_F2)
@pytest.mark.parametrize("diagnosis", DIAGNOSES)
def test_clean_edits_are_held_by_content_checks(variant, diagnosis):
    if variant == "diagnosis_upgrade" and diagnosis == "dengue":
        pytest.skip("upgrading dengue to dengue changes nothing")
    files, forgery = forge(make_claim("F", diagnosis, 77), "F2", variant, seed=5)
    report = run(files)
    assert report.verdict == "hold", forgery.description
    assert not any(f.checker == 1 for f in report.flags), "a clean edit leaves no file traces"
    assert any(f.checker in (2, 3) for f in report.flags)


def test_known_gap_pharmacy_quantities_are_not_caught_yet():
    files, _ = forge(make_claim("F", "dengue", 77), "F2", "pharmacy_qty", seed=5)
    assert run(files).verdict == "pass"


@pytest.mark.parametrize("variant", F5_VARIANTS)
@pytest.mark.parametrize("diagnosis", DIAGNOSES)
def test_pdf_overlay_edits_are_found_by_editing_signs(variant, diagnosis):
    files, forgery = forge(make_claim("F", diagnosis, 91), "F5", variant, seed=3)
    report = run(files)
    assert report.verdict == "hold"
    overprint = [f for f in report.flags if f.code == "pdf_overprint"]
    assert overprint and overprint[0].documents == [forgery.document]
    assert any(f.checker == 2 for f in report.flags), "the visible new value should also disagree"


def test_evidence_names_the_contradiction():
    files, _ = forge(make_claim("F", "dengue", 12), "F2", "lab_value", seed=1)
    flag = next(f for f in run(files).flags if f.code == "quoted_value_mismatch")
    assert "lab_report_1.pdf" in flag.documents and "discharge_summary.pdf" in flag.documents
    assert "platelet" in flag.detail.lower()


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract not installed")
def test_scanned_image_is_read_with_ocr():
    files = render_claim(make_claim("S", "typhoid", 5))
    page = pymupdf.open(stream=files["hospital_bill.pdf"], filetype="pdf")[0]
    files["hospital_bill.png"] = page.get_pixmap(dpi=200).tobytes("png")
    del files["hospital_bill.pdf"]
    report = run(files)
    bill = next(d for d in report.documents if d.file_name == "hospital_bill.png")
    assert bill.doc_type == "hospital_bill"
    assert bill.total is not None and len(bill.items) >= 5
    assert any("not checked for image files" in n for n in report.notes)


def test_rejects_bad_uploads():
    with pytest.raises(InvalidClaim):
        analyze([])
    with pytest.raises(InvalidClaim, match="not a PDF"):
        analyze([("notes.txt", b"just some text")])
    with pytest.raises(InvalidClaim, match="empty"):
        analyze([("empty.pdf", b"")])
    with pytest.raises(InvalidClaim, match="at most"):
        analyze([(f"f{i}.pdf", b"%PDF-") for i in range(13)])


def test_unknown_diagnosis_gets_a_note_not_a_flag():
    claim = make_claim("U", "typhoid", 3)
    claim.diagnosis_text = "Acute gastroenteritis"
    report = run(render_claim(claim))
    assert not any(f.checker == 3 for f in report.flags)
    assert any("No medical rules yet" in n for n in report.notes)


def test_duplicate_and_unsafe_file_names_are_cleaned():
    files = render_claim(make_claim("N", "dengue", 4))
    pdf = files["hospital_bill.pdf"]
    report, sources = analyze([("../../etc/bill.pdf", pdf), ("bill.pdf", pdf), ("weird&name?.pdf", pdf)])
    assert [s.name for s in sources] == ["bill.pdf", "bill-1.pdf", "weird_name_.pdf"]
