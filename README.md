# MedCore

Hospitals seal documents with a signed QR code. Anyone can verify them. Insurers check every claim.

MedCore fights forged health documents in two layers:

- **Prevent.** A hospital or lab installs MedCore, and every document it makes gets a QR seal. The seal holds the document's key facts and an Ed25519 signature only that issuer can create, and it is recorded in a hash-chained public log.
- **Detect.** An insurer checks a whole claim file. Each seal is checked against the printed page. Every document, sealed or not, then goes through three content checks: editing signs, whether the documents agree, and whether the medicine fits.

New to the project? Start with **[demo/DEMO_GUIDE.md](demo/DEMO_GUIDE.md)**: the screens, the code walkthrough, the demo script and likely viva questions.

## The four screens

| # | Screen | For | Does |
| --- | --- | --- | --- |
| 1 | Issue | Hospital or lab | Seals a PDF: signs its facts, stamps the QR code, writes the log |
| 2 | Verify | Anyone | Checks one document's seal against the page, step by step |
| 3 | Claim check | Insurer | Seals plus three content checks on a whole claim file |
| 4 | Registry and log | Administrator | Issuers and keys, the public log, revocation, issuing alerts |

## What makes a seal more than a QR code

1. **Page comparison.** Every signed fact, and a fingerprint of all the text on the page, is compared with the page as printed. A real QR code copied onto an edited page is caught.
2. **Stay binding.** Each seal names the hospital stay it belongs to. A genuine report from another patient's stay is caught in the claim check.
3. **Public log.** Every seal is logged as it is made, and each entry's hash covers the one before it, so an edited or deleted entry is detected. A seal signed with a stolen key, but never logged, is caught.
4. **Revocation.** A hospital can revoke a seal it issued by mistake.
5. **Issuing alerts.** An issuer sealing unusually many documents in an hour is flagged.
6. **A second layer.** Documents without seals still get the three content checks.

## Put it online

**Render (a public website, free).** Click the button, sign in to Render with GitHub, and press **Apply**. Render builds the `Dockerfile` and gives you a link like `https://medcore-xxxx.onrender.com` to share. It also creates an admin token (under Environment → `MEDCORE_ADMIN_TOKEN`). That token is needed on the Registry screen to register, suspend or revoke. Free services sleep when idle, so the first visit can take about a minute. Uploads are cleared on every restart, and the demo data loads again.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/crastaralston/medcore)

**GitHub Codespaces (runs inside GitHub, nothing to install).** On the repository page, click **Code → Codespaces → Create codespace on main**. The app builds and opens on port 8000 by itself.

**Any server with Docker:** `docker build -t medcore . && docker run -p 8000:8000 -e MEDCORE_ADMIN_TOKEN=choose-one medcore`

GitHub Pages cannot host this app, because it serves only static files and MedCore needs its Python server.

## Quick start

Requirements: Python 3.11+, Node.js 22+. Optional: [Tesseract OCR](https://github.com/tesseract-ocr/tesseract), only for reading photos and scans.

```bash
python3 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -e "backend[dev]"
cd frontend && npm install && npm run build && cd ..
uvicorn medcore_verify.api:app --app-dir backend --port 8000
```

Open http://localhost:8000. The demo issuers and demo seals load automatically from `demo/keys/`. To reset to a clean demo, stop the server and delete `data/`.

For frontend development with hot reload, run the API as above and, in a second terminal, `npm --prefix frontend run dev`, then open http://localhost:5173.

## Commands

| What | Command (from `backend/`) |
| --- | --- |
| Run all tests (92) | `pytest` |
| Rebuild the demo pack | `python -m medcore_verify.datagen demo --out ../demo` |
| Generate an evaluation dataset | `python -m medcore_verify.datagen dataset --out ../data/claims --per-diagnosis 30` |
| Score the content checkers | `python -m medcore_verify.evaluation --data ../data/claims --out ../data/results.md` |
| Lint the frontend (from `frontend/`) | `npm run lint` |

## Results

**Seal checks**, as tested in `tests/test_seal.py` and `tests/test_api.py`:

| Attack | Result |
| --- | --- |
| Real QR copied onto an edited page | Altered, with the changed fact named |
| A small text change outside the signed fields | Altered (page fingerprint) |
| A forger's own QR code | Unregistered issuer |
| QR contents edited | Invalid signature |
| Signed with a real key but never logged | Not in the public log |
| A revoked seal | Revoked |
| A log entry edited or deleted | Log broken at that entry |

QR codes decoded in 300 of 300 sealed PDFs, and in scans from 100 to 400 dpi.

**Content checks** on 390 synthetic claims (no seals). A cell is the share held for review:

| Group | Claims | Checker 1 only | Checker 2 only | Checker 3 only | Checkers 2 + 3 | All three |
| --- | --- | --- | --- | --- | --- | --- |
| Genuine (false alarms) | 90 | 0% | 0% | 0% | 0% | 0% |
| All F2 clean edits | 210 | **0%** | 71% | 14% | **86%** | 86% |
| All F5 PDF overlay edits | 90 | 100% | 100% | 0% | 100% | 100% |

**Read these honestly.** The same team wrote the forgeries and the rules, so these numbers show the system works end to end. They are not evidence of real-world accuracy.

## How it is built

```
backend/medcore_verify/
  reading/loader.py      PDF text layer or Tesseract OCR -> text lines; detects overprinted text
  reading/extract.py     document type + fields (patient, dates, doctor, diagnosis, tests, bill lines, totals)
  seal/crypto.py         Ed25519 keys, the signed token in the QR code, the key store
  seal/facts.py          which facts each document type signs; the page text fingerprint
  seal/qr.py             stamping the QR code on a PDF; finding it in PDFs, scans and photos
  seal/registry.py       issuers, the hash-chained public log, revocation, alerts, demo seeding
  seal/service.py        seal_pdf(), check_seal(), and seal flags for the claim check
  checks/forensics.py    check 1: editing signs inside PDFs
  checks/agreement.py    check 2: cross-document agreement
  checks/medical.py      check 3: medical plausibility, driven by checks/knowledge.json
  pipeline.py            runs one claim through seals and the three checks
  api.py, db.py          FastAPI app; SQLite by default, PostgreSQL via DATABASE_URL
  datagen/               synthetic claims, forgeries, and the demo pack builder
  evaluation.py          scores each content checker alone and combined
backend/tests/           92 tests
frontend/src/            React + TypeScript + Tailwind; one file per screen in screens/
demo/                    sample claims, Verify documents, demo keys, page pictures, the demo guide
```

**Configuration** (environment variables): `MEDCORE_DATA_DIR` (uploads, sealed files, new issuers' keys and the SQLite file; default `data/`), `MEDCORE_DEMO_DIR` (default `demo/`), `DATABASE_URL`, `MEDCORE_CORS`.

**Security notes:**
- Uploads are limited to 12 files per claim and 15 MB per file.
- File names are sanitised and every file path is checked against traversal.
- Private keys are written with owner-only permissions.
- The demo keys in `demo/keys/` are for the fictional demo issuers only. A real hospital keeps its own key on its own machine.
- Set `MEDCORE_ADMIN_TOKEN` on any public deployment: registering, suspending and revoking then need that token. Revocations are not yet signed by the issuer itself (future scope).

## Libraries used

FastAPI, SQLAlchemy, cryptography (Ed25519), qrcode, zxing-cpp and OpenCV (QR reading), PyMuPDF (AGPL), Tesseract via pytesseract, RapidFuzz, ReportLab and Faker (test data only), React, Vite, Tailwind CSS.

## Data and ethics

Every document, hospital, lab, pharmacy and key in this repository is synthetic. Every page carries a "SYNTHETIC SAMPLE" footer. The medical rules in `knowledge.json` are simplified for checking claim documents and are not clinical advice. A flag means "check this", never "fraud".
