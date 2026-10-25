"""Builds the demo pack:

    demo/claims/    nine claim folders (six unsealed, three sealed), each with ABOUT.md
    demo/verify/    single documents that show each kind of seal result on the Verify screen
    demo/keys/      demo issuers, their demo signing keys, and the log of the demo seals
    demo/pictures/  a picture of every page

Every ABOUT.md is written from what the program actually reads and reports, so the
demo notes always match the software's real behaviour.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pymupdf

from ..db import Store
from ..models import CHECKER_NAMES, ExtractedDoc, Report
from ..pipeline import analyze
from ..seal import crypto, qr
from ..seal.registry import Registry, export_log, slugify
from ..seal.service import SealResult, seal_pdf, verify_upload
from .__main__ import build_samples, write_claim
from .forge import forge
from .render import render_claim
from .scenarios import HOSPITALS, LABS, PHARMACIES, Claim, make_claim

DOC_PURPOSE = {
    "discharge_summary": "Written by the hospital when the patient goes home. It states the diagnosis, the dates "
                         "of the stay, the treating doctor and the key lab results.",
    "hospital_bill": "The hospital's final bill: every charge for the stay, line by line, with a grand total.",
    "lab_report": "A test report from the laboratory: what was tested, the result, and the normal range.",
    "pharmacy_bill": "The chemist's invoice for medicines bought for this treatment.",
}
SEVERITY_WORD = {"high": "Serious", "medium": "Check", "low": "Minor"}
SEAL_WORD = {"genuine": "valid seal, matches the page", "no_seal": "no seal"}


def demo_issuers() -> list[dict]:
    out = []
    for kind, items in (("hospital", HOSPITALS), ("lab", LABS), ("pharmacy", PHARMACIES)):
        out += [{"id": slugify(name), "name": name, "kind": kind, "address": address} for name, address in items]
    return out


def issuer_for(claim: Claim, file_name: str) -> str:
    if file_name.startswith("lab_report"):
        return slugify(claim.lab[0])
    if file_name.startswith("pharmacy"):
        return slugify(claim.pharmacy[0])
    return slugify(claim.hospital[0])


def seal_claim(registry: Registry, keys: crypto.KeyStore, claim: Claim,
               files: dict[str, bytes]) -> tuple[dict[str, bytes], dict[str, SealResult]]:
    sealed, results = {}, {}
    for name, data in files.items():
        r = seal_pdf(registry, keys, issuer_for(claim, name), name, data, stay_id=claim.bill_no)
        sealed[name], results[name] = r.pdf, r
    return sealed, results


def _money(n: float | None) -> str:
    return f"Rs. {n:,.2f}" if n is not None else "not found"


def _describe(d: ExtractedDoc) -> list[str]:
    facts = []
    if d.seal:
        facts.append(f"QR seal: {SEAL_WORD.get(d.seal['status'], d.seal['title'])}"
                     + (f" (sealed by {d.seal['issuer']['name']}, stay {d.seal['stay_id']})"
                        if d.seal.get("issuer") and d.seal["status"] == "genuine" else ""))
    if d.patient_name:
        facts.append(f"Patient: {d.patient_name}" + (f", {d.age}, {d.sex}" if d.age else ""))
    if d.hospital or d.lab_name:
        facts.append(f"Issued by: {d.hospital or d.lab_name}")
    if d.admission and d.discharge:
        facts.append(f"Stay: {d.admission:%d %b %Y} to {d.discharge:%d %b %Y}")
    if d.diagnosis:
        facts.append(f"Diagnosis: {d.diagnosis}")
    if d.procedure:
        facts.append(f"Procedure: {d.procedure}")
    if d.quoted_values:
        facts.append("Lab values it quotes: " + "; ".join(f"{k} {', '.join(v)}" for k, v in d.quoted_values.items()))
    if d.collected:
        facts.append(f"Sample taken: {d.collected:%d %b %Y}" + (f", reported {d.doc_date:%d %b %Y}" if d.doc_date else ""))
    if d.tests:
        facts.append("Results: " + "; ".join(f"{t.raw_name} {t.value} {t.unit}".strip() for t in d.tests))
    if d.items:
        facts.append(f"{len(d.items)} line items, total {_money(d.total)}")
    if d.doc_type == "pharmacy_bill" and d.doc_date:
        facts.append(f"Invoice date: {d.doc_date:%d %b %Y}")
    return facts


HOW_FAKED = {
    "F2": "the document was re-printed with the new value, so the file itself looks perfect. "
          "Only checks 2 and 3 can catch this, unless the document was sealed.",
    "F5": "a white box was painted over the real value inside the PDF and a new value typed on top, "
          "then the file was saved again. The original value is still hidden in the file.",
    "S1": "after sealing, the page was re-printed with a changed value and the genuine QR code was copied onto it. "
          "The QR code is real, but it no longer matches the page.",
    "S2": "a genuine, correctly sealed lab report from another patient's hospital stay was put into this claim.",
}


def _about(name: str, truth: dict, report: Report) -> str:
    out = [f"# {name}", ""]
    if truth["genuine"]:
        out += [f"**What this claim is:** {truth['description']}. Use it to show that honest claims pass.", ""]
    else:
        out += [f"**What was faked:** {truth['description']}.", "",
                f"**Which document was changed:** `{truth['changed_document']}`", "",
                f"**How it was faked:** {HOW_FAKED[truth['forgery_type']]}", ""]
    out += ["## The documents in this folder", ""]
    for d in report.documents:
        out += [f"### `{d.file_name}` - {d.doc_type.replace('_', ' ')}", "", DOC_PURPOSE.get(d.doc_type, ""), ""]
        out += [f"- {f}" for f in _describe(d)] + [""]
    out += ["## What MedCore reports in the Claim check screen", "", f"**Verdict: {report.verdict_label}**", ""]
    if not report.flags:
        out.append("No problems. Every document agrees with the others and with the diagnosis.")
    for i, f in enumerate(report.flags, 1):
        out.append(f"{i}. **{SEVERITY_WORD[f.severity]}: {f.title}** (check {f.checker}, {CHECKER_NAMES[f.checker]})  ")
        out.append(f"   {f.detail}")
    if not truth["genuine"] and report.verdict != "hold":
        out += ["", "This forgery is **not caught** by the current version. That is expected: it is listed as "
                    "future scope. Say so openly in the demo; it shows you know the limits."]
    if report.notes:
        out += ["", "Notes: " + " ".join(report.notes)]
    return "\n".join(out) + "\n"


def _sealed_claims(registry: Registry, keys: crypto.KeyStore, claims_dir: Path, seed: int) -> None:
    # 07: genuine, every document sealed.
    claim = make_claim("07", "dengue", seed + 6)
    files, _ = seal_claim(registry, keys, claim, render_claim(claim))
    write_claim(claims_dir / "07_sealed_genuine_dengue", files,
                {"claim_id": "07", "diagnosis": "dengue", "genuine": True, "sealed": True, "forgery_type": None,
                 "variant": None, "changed_document": None,
                 "description": "A genuine claim where every document carries a valid QR seal"})

    # 08: sealed, then the lab report edited and the real QR copied onto the edited page.
    claim = make_claim("08", "dengue", seed + 7)
    files, results = seal_claim(registry, keys, claim, render_claim(claim))
    forged, forgery = forge(claim, "F2", "lab_value", seed=seed + 107)
    genuine = results["lab_report_1.pdf"]
    files["lab_report_1.pdf"] = qr.stamp(forged["lab_report_1.pdf"], genuine.token, genuine.doc_id)
    write_claim(claims_dir / "08_sealed_then_edited_dengue", files,
                {"claim_id": "08", "diagnosis": "dengue", "genuine": False, "sealed": True, "forgery_type": "S1",
                 "variant": "sealed_then_edited", "changed_document": "lab_report_1.pdf",
                 "description": f"After sealing, {forgery.description[0].lower()}{forgery.description[1:]}, "
                                "and the original QR code was copied onto the edited page"})

    # 09: a genuine sealed lab report from another patient's stay, swapped in.
    claim = make_claim("09", "typhoid", seed + 8)
    files, _ = seal_claim(registry, keys, claim, render_claim(claim))
    other = make_claim("09b", "typhoid", seed + 9)
    other_files = render_claim(other)
    files["lab_report_1.pdf"] = seal_pdf(registry, keys, issuer_for(other, "lab_report_1.pdf"), "lab_report_1.pdf",
                                         other_files["lab_report_1.pdf"], stay_id=other.bill_no).pdf
    write_claim(claims_dir / "09_borrowed_sealed_report_typhoid", files,
                {"claim_id": "09", "diagnosis": "typhoid", "genuine": False, "sealed": True, "forgery_type": "S2",
                 "variant": "borrowed_sealed_report", "changed_document": "lab_report_1.pdf",
                 "description": f"lab_report_1.pdf is a genuine sealed report, but it belongs to {other.patient_name}'s "
                                f"stay {other.bill_no}, not this patient's stay {claim.bill_no}"})


VERIFY_FILES = [
    ("1_genuine_sealed_lab_report.pdf", "A lab report sealed by its lab and not touched since."),
    ("2_edited_after_sealing.pdf", "The same kind of report: after sealing, the platelet count was changed and the "
                                   "real QR code copied onto the edited page."),
    ("3_fake_qr_unregistered_lab.pdf", "A forger made their own QR code, claiming to be 'TrustMe Diagnostics', "
                                       "which is not a registered lab."),
    ("4_stolen_key_never_logged.pdf", "Signed with a real lab's key, as if the key had been stolen, but never "
                                      "recorded in the public log."),
    ("5_unsealed_lab_report.pdf", "An ordinary lab report with no QR code at all."),
]


def _verify_files(registry: Registry, keys: crypto.KeyStore, claims_dir: Path, out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copy(claims_dir / "07_sealed_genuine_dengue" / "lab_report_1.pdf", out / VERIFY_FILES[0][0])
    shutil.copy(claims_dir / "08_sealed_then_edited_dengue" / "lab_report_1.pdf", out / VERIFY_FILES[1][0])
    plain = (claims_dir / "01_genuine_dengue" / "lab_report_1.pdf").read_bytes()
    sealed = (claims_dir / "07_sealed_genuine_dengue" / "lab_report_1.pdf").read_bytes()
    from ..reading.loader import load
    token = qr.find_tokens(load("x.pdf", sealed))[0]
    payload, _, _ = crypto.parse_token(token)

    fake = dict(payload, iss="trustme-diagnostics", id="FAKEQR234567")
    (out / VERIFY_FILES[2][0]).write_bytes(qr.stamp(plain, crypto.sign_token(fake, crypto.new_private_key()), fake["id"]))
    stolen = dict(payload, id="NTLGGD234567")
    real_key = keys.load(payload["iss"])
    (out / VERIFY_FILES[3][0]).write_bytes(qr.stamp(plain, crypto.sign_token(stolen, real_key), stolen["id"]))
    shutil.copy(claims_dir / "01_genuine_dengue" / "lab_report_1.pdf", out / VERIFY_FILES[4][0])

    lines = ["# Documents for the Verify screen", "",
             "Upload these one at a time on the **Verify** screen. Each shows a different result.", "",
             "| File | What it is | What Verify says |", "| --- | --- | --- |"]
    for name, what in VERIFY_FILES:
        check, _, _ = verify_upload(registry, name, (out / name).read_bytes())
        lines.append(f"| `{name}` | {what} | **{check.title}**: {check.detail} |")
    lines += ["", "To show revocation: open **Registry and log**, press *Revoke* on a seal, then verify "
                  "`1_genuine_sealed_lab_report.pdf` again. It now says the seal was revoked."]
    (out / "ABOUT.md").write_text("\n".join(lines) + "\n")


def build_demo(demo_dir: Path, seed: int = 41) -> list[str]:
    claims_dir, keys_dir, pictures_dir = demo_dir / "claims", demo_dir / "keys", demo_dir / "pictures"
    build_samples(claims_dir, seed=seed)

    # Demo issuers keep their keys between rebuilds, so a running server's registry stays valid.
    keys = crypto.KeyStore(keys_dir)
    issuers = demo_issuers()
    for item in issuers:
        if keys.load(item["id"]) is None:
            keys.save(item["id"], crypto.new_private_key())
    (keys_dir / "issuers.json").write_text(json.dumps(issuers, indent=2) + "\n")
    (keys_dir / "README.md").write_text(
        "# Demo keys\n\nSigning keys for the fictional demo hospitals, labs and pharmacies, plus the log of the "
        "demo seals.\nThey exist only so the demo works out of the box. Never use them for real documents: a real "
        "hospital keeps its own key on its own machine.\n")

    with tempfile.TemporaryDirectory() as tmp:
        registry = Registry(Store(f"sqlite:///{Path(tmp) / 'demo.db'}"))
        for item in issuers:
            registry.register(item["name"], item["kind"], item["address"], crypto.public_pem(keys.load(item["id"])),
                              issuer_id=item["id"])
        _sealed_claims(registry, keys, claims_dir, seed)
        _verify_files(registry, keys, claims_dir, demo_dir / "verify")
        (keys_dir / "log.json").write_text(json.dumps(export_log(registry), indent=2) + "\n")

        if pictures_dir.exists():
            shutil.rmtree(pictures_dir)
        pictures_dir.mkdir(parents=True)
        names = []
        for folder in sorted(p for p in claims_dir.iterdir() if p.is_dir()):
            files = [(p.name, p.read_bytes()) for p in sorted(folder.glob("*.pdf"))]
            report, _ = analyze(files, registry)
            truth = json.loads((folder / "truth.json").read_text())
            (folder / "ABOUT.md").write_text(_about(folder.name, truth, report))
            for pdf_name, data in files:
                page = pymupdf.open(stream=data, filetype="pdf")[0]
                page.get_pixmap(dpi=90).save(pictures_dir / f"{folder.name}__{pdf_name[:-4]}.png")
            names.append(folder.name)
    return names
