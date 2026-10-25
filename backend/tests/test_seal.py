import shutil
import zlib
from datetime import datetime, timedelta, timezone

import pymupdf
import pytest
from sqlalchemy import update

from medcore_verify.datagen.forge import forge
from medcore_verify.datagen.render import render_claim
from medcore_verify.datagen.scenarios import make_claim
from medcore_verify.db import LedgerEntry, Store
from medcore_verify.pipeline import analyze
from medcore_verify.seal import crypto, qr
from medcore_verify.seal.registry import BURST_LIMIT, Registry, RegistryError
from medcore_verify.seal.service import SealError, seal_pdf, verify_upload


@pytest.fixture
def env(tmp_path):
    registry = Registry(Store(f"sqlite:///{tmp_path / 'seal.db'}"))
    keys = crypto.KeyStore(tmp_path / "keys")
    for issuer_id, kind in (("lab", "lab"), ("hospital", "hospital"), ("pharmacy", "pharmacy")):
        key = crypto.new_private_key()
        keys.save(issuer_id, key)
        registry.register(f"Test {kind}", kind, "Thane", crypto.public_pem(key), issuer_id)
    claim = make_claim("C", "dengue", 7)
    return registry, keys, claim, render_claim(claim)


def seal(env, name="lab_report_1.pdf", issuer="lab"):
    registry, keys, claim, files = env
    return seal_pdf(registry, keys, issuer, name, files[name], stay_id=claim.bill_no)


def status(registry, data, name="doc.pdf"):
    check, _, _ = verify_upload(registry, name, data)
    return check


def test_genuine_seal_verifies_field_by_field(env):
    result = seal(env)
    check = status(env[0], result.pdf)
    assert check.status == "genuine"
    assert check.text_matches is True
    assert {f.label for f in check.fields} >= {"Patient name", "Age", "Platelet count", "NS1 antigen"}
    assert all(f.status == "match" for f in check.fields)
    assert check.stay_id == env[2].bill_no


def test_copied_qr_on_edited_page_is_altered(env):
    registry, _, claim, _ = env
    result = seal(env)
    forged, _ = forge(claim, "F2", "lab_value", seed=3)
    check = status(registry, qr.stamp(forged["lab_report_1.pdf"], result.token, result.doc_id))
    assert check.status == "altered"
    diff = [f for f in check.fields if f.status == "different"]
    assert [f.label for f in diff] == ["Platelet count"]


def test_any_text_change_is_caught_even_outside_signed_fields(env):
    result = seal(env)
    doc = pymupdf.open(stream=result.pdf, filetype="pdf")
    page = doc[0]
    hit = page.search_for("Referred By")[0]
    page.add_redact_annot(hit, text="Referred  By")  # a tiny change to text that is not a signed field
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
    check = status(env[0], doc.tobytes())
    assert check.status == "altered" and check.text_matches is False


def test_forger_cannot_make_a_valid_seal(env):
    registry, _, _, files = env
    payload = dict(seal(env).payload, iss="trustme-lab")
    fake = qr.stamp(files["lab_report_1.pdf"], crypto.sign_token(payload, crypto.new_private_key()), payload["id"])
    assert status(registry, fake).status == "unknown_issuer"


def test_changing_the_qr_contents_breaks_the_signature(env):
    registry, _, _, files = env
    result = seal(env)
    payload, _, signature = crypto.parse_token(result.token)
    payload["f"]["tests"]["platelet count"] = "30,000"
    token = f"MCS1.{crypto._b64(zlib.compress(crypto.canonical(payload)))}.{crypto._b64(signature)}"
    assert status(registry, qr.stamp(files["lab_report_1.pdf"], token, result.doc_id)).status == "bad_signature"


def test_stolen_key_seal_is_not_in_the_log(env):
    registry, keys, _, files = env
    payload = dict(seal(env).payload, id="STLNKY234567")
    token = crypto.sign_token(payload, keys.load("lab"))
    assert status(registry, qr.stamp(files["lab_report_1.pdf"], token, payload["id"])).status == "unlogged"


def test_revoked_seal(env):
    registry = env[0]
    result = seal(env)
    registry.revoke(result.doc_id, "Issued for the wrong patient")
    check = status(registry, result.pdf)
    assert check.status == "revoked" and "wrong patient" in check.detail
    with pytest.raises(RegistryError, match="already revoked"):
        registry.revoke(result.doc_id, "again")


def test_random_qr_and_no_qr(env):
    registry, _, _, files = env
    assert status(registry, files["lab_report_1.pdf"]).status == "no_seal"
    other = qr.stamp(files["lab_report_1.pdf"], "https://example.com/report/123", "AAAAAAAAAAAA")
    assert status(registry, other).status == "unreadable"


def test_sealing_rules(env):
    registry, keys, _, files = env
    result = seal(env)
    with pytest.raises(SealError, match="already carries a QR"):
        seal_pdf(registry, keys, "lab", "again.pdf", result.pdf)
    registry.set_status("lab", "suspended")
    with pytest.raises(SealError, match="suspended"):
        seal(env)
    registry.set_status("lab", "active")
    with pytest.raises(SealError, match="not registered"):
        seal_pdf(registry, keys, "nobody", "x.pdf", files["lab_report_1.pdf"])
    with pytest.raises(SealError, match="Only PDF"):
        png = pymupdf.open(stream=files["lab_report_1.pdf"], filetype="pdf")[0].get_pixmap(dpi=100).tobytes("png")
        seal_pdf(registry, keys, "lab", "x.png", png)


def test_installed_key_must_match_registered_key(env):
    registry, keys, _, _ = env
    keys.save("lab", crypto.new_private_key())  # someone replaced the key file
    with pytest.raises(SealError, match="does not match"):
        seal(env)


def test_log_is_tamper_evident(env):
    registry = env[0]
    for name in ("lab_report_1.pdf", "lab_report_2.pdf"):
        seal(env, name)
    assert registry.verify_chain() == (True, [])
    with registry.store.session() as s, s.begin():
        s.execute(update(LedgerEntry).where(LedgerEntry.seq == 1).values(doc_type="hospital_bill"))
    intact, broken = registry.verify_chain()
    assert not intact and broken == [1]


def test_deleting_a_log_entry_is_detected(env):
    registry = env[0]
    for name in ("lab_report_1.pdf", "lab_report_2.pdf", "pharmacy_bill.pdf"):
        seal(env, name, issuer="pharmacy" if name.startswith("pharmacy") else "lab")
    with registry.store.session() as s, s.begin():
        s.delete(s.get(LedgerEntry, 2))
    intact, broken = registry.verify_chain()
    assert not intact and broken == [3]


def test_burst_alert(env):
    registry = env[0]
    start = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
    for i in range(BURST_LIMIT + 1):
        registry.append("seal", f"BURST{i:07d}", "lab", "lab_report", None, "0" * 64,
                        at=start + timedelta(minutes=i))
    alerts = registry.alerts()
    assert len(alerts) == 1 and alerts[0]["issuer_id"] == "lab"
    registry.append("seal", "CALM00000001", "hospital", "hospital_bill", None, "0" * 64)
    assert [a["issuer_id"] for a in registry.alerts()] == ["lab"]


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract not installed")
def test_scan_of_a_sealed_page_verifies(env):
    result = seal(env)
    png = pymupdf.open(stream=result.pdf, filetype="pdf")[0].get_pixmap(dpi=200).tobytes("png")
    check = status(env[0], png, "scan.png")
    assert check.status == "genuine" and check.text_matches is None


def seal_all(env, claim, files):
    registry, keys, _, _ = env
    issuer = {"lab": "lab", "pha": "pharmacy"}
    return {name: seal_pdf(registry, keys, issuer.get(name[:3], "hospital"), name, data, stay_id=claim.bill_no).pdf
            for name, data in files.items()}


def test_claim_check_with_all_documents_sealed(env):
    registry, _, claim, files = env
    report, _ = analyze(list(seal_all(env, claim, files).items()), registry)
    assert report.verdict == "pass", [f.title for f in report.flags]
    assert all(d.seal["status"] == "genuine" for d in report.documents)


def test_claim_check_catches_a_report_from_another_stay(env):
    registry, _, claim, files = env
    sealed = seal_all(env, claim, files)
    other = make_claim("O", "dengue", 99)
    sealed["lab_report_1.pdf"] = seal_all(env, other, {"lab_report_1.pdf": render_claim(other)["lab_report_1.pdf"]})[
        "lab_report_1.pdf"]
    report, _ = analyze(list(sealed.items()), registry)
    codes = {f.code for f in report.flags}
    assert report.verdict == "hold" and "seal_stay_mismatch" in codes and "name_mismatch" in codes


def test_claim_check_without_registry_ignores_seals(env):
    report, _ = analyze(list(env[3].items()))
    assert all(d.seal is None for d in report.documents)


def test_qr_codes_decode_reliably(env):
    """Regression: OpenCV alone missed about 1 code in 20. Every one of these must decode."""
    from medcore_verify.models import SourceFile
    from medcore_verify.seal.service import new_doc_id

    _, keys, _, files = env
    key = keys.load("lab")
    for i in range(60):
        doc_id = new_doc_id()
        token = crypto.sign_token({"v": 1, "id": doc_id, "n": i, "pad": "x" * (i * 5)}, key)
        sealed = qr.stamp(files["lab_report_1.pdf"], token, doc_id)
        assert qr.find_tokens(SourceFile("x.pdf", "pdf", sealed)) == [token], i
