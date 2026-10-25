"""HTTP API. Run with:  uvicorn medcore_verify.api:app --app-dir backend --port 8000

Four parts, one per screen:
  Issue      POST /api/seal                 a hospital or lab seals a PDF with a signed QR code
  Verify     POST /api/verify               anyone checks one document's seal against the page
  Claims     POST /api/checks               an insurer checks a whole claim file (seals + three checks)
  Registry   /api/issuers, /api/log         registered issuers, the public log, revocation, alerts

Settings (environment variables):
  MEDCORE_DATA_DIR     uploads, sealed files, issuer keys and the SQLite file (default: ../data)
  MEDCORE_DEMO_DIR     the demo pack: sample claims and demo issuers (default: ../demo)
  DATABASE_URL         SQLAlchemy URL, e.g. postgresql+psycopg://user:pass@host/medcore
  MEDCORE_CORS         comma-separated origins allowed to call the API (default: the Vite dev server)
  MEDCORE_ADMIN_TOKEN  if set, registering, suspending and revoking need this token (set it when public)
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import uuid
from pathlib import Path

import pymupdf
from fastapi import Body, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .db import ClaimCheck, Store, now
from .models import SourceFile
from .pipeline import MAX_FILES, InvalidClaim, analyze
from .reading.loader import MAX_FILE_BYTES, UnreadableFile
from .seal import crypto, qr
from .seal.registry import KINDS, Registry, RegistryError, entry_json, issuer_json, seed_from
from .seal.service import SealError, seal_pdf, verify_upload

BACKEND_DIR = Path(__file__).resolve().parent.parent
SAFE_NAME = re.compile(r"^[\w\-. ()]{1,120}$")
DOC_ID = re.compile(r"^[A-Z2-9]{12}$")


def _tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def _read_upload(f: UploadFile) -> tuple[str, bytes]:
    data = f.file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail=f"{f.filename} is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB")
    return f.filename or "document", data


def create_app(data_dir: Path | None = None, database_url: str | None = None,
               demo_dir: Path | None = None, admin_token: str | None = None) -> FastAPI:
    admin_token = admin_token if admin_token is not None else os.environ.get("MEDCORE_ADMIN_TOKEN", "")
    data_dir = (data_dir or Path(os.environ.get("MEDCORE_DATA_DIR", BACKEND_DIR.parent / "data"))).resolve()
    demo_dir = (demo_dir or Path(os.environ.get("MEDCORE_DEMO_DIR", BACKEND_DIR.parent / "demo"))).resolve()
    uploads, sealed_dir, samples = data_dir / "uploads", data_dir / "sealed", demo_dir / "claims"
    for d in (uploads, sealed_dir):
        d.mkdir(parents=True, exist_ok=True)
    store = Store(database_url or os.environ.get("DATABASE_URL", f"sqlite:///{data_dir / 'medcore.db'}"))
    registry = Registry(store)
    # Keys made in the Registry screen live in data/keys; the demo issuers' keys ship in demo/keys.
    keys = crypto.KeyStore(data_dir / "keys", demo_dir / "keys")
    seed_from(registry, demo_dir / "keys")

    app = FastAPI(title="MedCore", version="0.2.0",
                  description="Seals health documents with signed QR codes and checks claim files for forgery.")
    origins = os.environ.get("MEDCORE_CORS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in origins if o.strip()],
                       allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"])
    app.state.store, app.state.registry = store, registry

    # ---- Claims (insurer) ----

    def save_check(label: str, files: list[tuple[str, bytes]], truth: dict | None) -> dict:
        try:
            report, sources = analyze(files, registry)
        except InvalidClaim as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        check_id = uuid.uuid4().hex
        folder = uploads / check_id
        (folder / "previews").mkdir(parents=True)
        _write_files(folder, sources)
        named = next((d for d in report.documents if d.patient_name), None)
        check = ClaimCheck(
            id=check_id, created_at=now(), label=label[:200], verdict=report.verdict,
            flag_count=len(report.flags), patient_name=named.patient_name if named else None,
            file_names=json.dumps([s.name for s in sources]), report_json=json.dumps(report.to_json()),
            truth_json=json.dumps(truth) if truth else None)
        store.add(check)
        return check.full()

    def check_folder(check_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", check_id) or store.get(check_id) is None:
            raise HTTPException(status_code=404, detail="No such check")
        return uploads / check_id

    def require_admin(token: str | None) -> None:
        """On a public deployment, registry changes need the admin token."""
        if admin_token and not secrets.compare_digest(token or "", admin_token):
            raise HTTPException(status_code=403, detail="This action needs the admin token. Enter it on the "
                                                        "Registry and log screen.")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "image_ocr": _tesseract_available(), "admin_locked": bool(admin_token)}

    @app.post("/api/checks", status_code=201)
    def create_check(files: list[UploadFile] = File(...), label: str = Form("")) -> dict:
        if len(files) > MAX_FILES:
            raise HTTPException(status_code=422, detail=f"A claim can have at most {MAX_FILES} documents.")
        return save_check(label.strip() or "Uploaded claim", [_read_upload(f) for f in files], None)

    @app.get("/api/checks")
    def list_checks(limit: int = 50) -> list[dict]:
        return [c.summary() for c in store.recent(max(1, min(limit, 200)))]

    @app.get("/api/checks/{check_id}")
    def get_check(check_id: str) -> dict:
        check_folder(check_id)
        return store.get(check_id).full()

    @app.delete("/api/checks/{check_id}", status_code=204)
    def delete_check(check_id: str) -> None:
        folder = check_folder(check_id)
        store.delete(check_id)
        shutil.rmtree(folder, ignore_errors=True)

    @app.get("/api/checks/{check_id}/files/{name}")
    def get_file(check_id: str, name: str) -> FileResponse:
        return FileResponse(_safe_child(check_folder(check_id), name))

    @app.get("/api/checks/{check_id}/previews/{name}")
    def get_preview(check_id: str, name: str) -> FileResponse:
        return FileResponse(_safe_child(check_folder(check_id) / "previews", f"{name}.png"), media_type="image/png")

    @app.get("/api/samples")
    def list_samples() -> list[dict]:
        out = []
        for folder in sorted(p for p in samples.glob("*") if p.is_dir()) if samples.exists() else []:
            truth_file = folder / "truth.json"
            truth = json.loads(truth_file.read_text()) if truth_file.exists() else {}
            out.append({"name": folder.name, "diagnosis": truth.get("diagnosis"), "sealed": truth.get("sealed", False),
                        "files": sorted(p.name for p in folder.glob("*.pdf"))})
        return out

    @app.get("/api/samples/{name}/files/{file}")
    def sample_file(name: str, file: str) -> FileResponse:
        return FileResponse(_safe_child(_safe_child(samples, name), file), media_type="application/pdf")

    @app.post("/api/samples/{name}/check", status_code=201)
    def check_sample(name: str) -> dict:
        folder = _safe_child(samples, name)
        if not folder.is_dir():
            raise HTTPException(status_code=404, detail="No such sample")
        files = [(p.name, p.read_bytes()) for p in sorted(folder.iterdir())
                 if p.suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg")]
        truth_file = folder / "truth.json"
        return save_check(f"Sample: {name}", files, json.loads(truth_file.read_text()) if truth_file.exists() else None)

    # ---- Issue (hospital or lab) ----

    @app.post("/api/seal", status_code=201)
    def seal(issuer_id: str = Form(...), stay_id: str = Form(""), file: UploadFile | None = File(None),
             sample_file: str = Form("")) -> dict:
        if file is not None:
            name, data = _read_upload(file)
        elif sample_file:
            folder, _, fname = sample_file.partition("/")
            path = _safe_child(_safe_child(samples, folder), fname)
            name, data = path.name, path.read_bytes()
        else:
            raise HTTPException(status_code=422, detail="Choose a PDF to seal.")
        try:
            result = seal_pdf(registry, keys, issuer_id, name, data, stay_id)
        except SealError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        (sealed_dir / f"{result.doc_id}.pdf").write_bytes(result.pdf)
        stem = Path(name).stem
        return {"doc_id": result.doc_id, "display_id": qr.display_id(result.doc_id), "payload": result.payload,
                "document": result.doc.to_json(), "issuer": issuer_json(registry.issuer(issuer_id)),
                "file_name": f"{stem}_sealed.pdf", "token_length": len(result.token)}

    @app.get("/api/sealed/{doc_id}.pdf")
    def sealed_pdf(doc_id: str, name: str = "sealed.pdf") -> FileResponse:
        path = sealed_dir / f"{_doc_id(doc_id)}.pdf"
        if not path.exists():
            raise HTTPException(status_code=404, detail="Not found")
        safe = name if SAFE_NAME.fullmatch(name) else "sealed.pdf"
        return FileResponse(path, media_type="application/pdf", filename=safe)

    @app.get("/api/sealed/{doc_id}/qr.png")
    def sealed_qr(doc_id: str) -> Response:
        path = sealed_dir / f"{_doc_id(doc_id)}.pdf"
        if not path.exists():
            raise HTTPException(status_code=404, detail="Not found")
        tokens = qr.find_tokens(SourceFile(path.name, "pdf", path.read_bytes()))
        if not tokens:
            raise HTTPException(status_code=404, detail="No QR code found")
        return Response(qr.qr_png(tokens[0], box=6), media_type="image/png")

    @app.get("/api/sealed/{doc_id}/preview.png")
    def sealed_preview(doc_id: str) -> Response:
        path = sealed_dir / f"{_doc_id(doc_id)}.pdf"
        if not path.exists():
            raise HTTPException(status_code=404, detail="Not found")
        doc = pymupdf.open(path)
        with doc:
            return Response(doc[0].get_pixmap(dpi=80).tobytes("png"), media_type="image/png")

    # ---- Verify (anyone) ----

    def verify_bytes(name: str, data: bytes) -> dict:
        try:
            check, doc, _ = verify_upload(registry, name, data)
        except UnreadableFile as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"file_name": name, "seal": check.to_json(), "document": doc.to_json()}

    @app.post("/api/verify")
    def verify(file: UploadFile = File(...)) -> dict:
        return verify_bytes(*_read_upload(file))

    verify_samples = demo_dir / "verify"

    @app.get("/api/verify-samples")
    def list_verify_samples() -> list[str]:
        return sorted(p.name for p in verify_samples.glob("*.pdf")) if verify_samples.exists() else []

    @app.post("/api/verify-samples/{name}")
    def verify_sample(name: str) -> dict:
        path = _safe_child(verify_samples, name)
        return verify_bytes(path.name, path.read_bytes())

    # ---- Registry and public log ----

    @app.get("/api/issuers")
    def list_issuers() -> list[dict]:
        counts = registry.sealed_counts()
        return [issuer_json(i, counts.get(i.id, 0)) | {"can_seal_here": keys.path(i.id) is not None}
                for i in registry.issuers()]

    @app.post("/api/issuers", status_code=201)
    def add_issuer(name: str = Body(...), kind: str = Body(...), address: str = Body(""),
                   x_admin_token: str | None = Header(None)) -> dict:
        require_admin(x_admin_token)
        key = crypto.new_private_key()
        try:
            issuer = registry.register(name, kind, address, crypto.public_pem(key))
        except RegistryError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        keys.save(issuer.id, key)
        return issuer_json(issuer) | {"can_seal_here": True}

    @app.post("/api/issuers/{issuer_id}/status")
    def set_issuer_status(issuer_id: str, status: str = Body(..., embed=True),
                          x_admin_token: str | None = Header(None)) -> dict:
        require_admin(x_admin_token)
        try:
            return issuer_json(registry.set_status(issuer_id, status))
        except RegistryError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/log")
    def log(limit: int = 100) -> dict:
        intact, broken = registry.verify_chain()
        names = {i.id: i.name for i in registry.issuers()}
        return {"intact": intact, "broken_at": broken, "alerts": registry.alerts(), "kinds": list(KINDS),
                "entries": [entry_json(e) | {"issuer": names.get(e.issuer_id, e.issuer_id),
                                             "display_id": qr.display_id(e.doc_id)}
                            for e in registry.entries(max(1, min(limit, 500)))]}

    @app.post("/api/log/{doc_id}/revoke", status_code=201)
    def revoke(doc_id: str, reason: str = Body("", embed=True), x_admin_token: str | None = Header(None)) -> dict:
        require_admin(x_admin_token)
        try:
            return entry_json(registry.revoke(_doc_id(doc_id), reason))
        except RegistryError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    def unknown_api_route(rest: str) -> None:
        raise HTTPException(status_code=404, detail="Not found")

    dist = Path(os.environ.get("MEDCORE_WEB_DIR", BACKEND_DIR.parent / "frontend" / "dist"))
    if dist.is_dir():  # production: serve the built web app from the same server
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app


def _doc_id(value: str) -> str:
    value = value.replace("-", "").upper()
    if not DOC_ID.fullmatch(value):
        raise HTTPException(status_code=404, detail="Not found")
    return value


def _write_files(folder: Path, sources: list[SourceFile]) -> None:
    for src in sources:
        (folder / src.name).write_bytes(src.data)
        if src.preview is not None:
            src.preview.save(folder / "previews" / f"{src.name}.png")


def _safe_child(parent: Path, name: str) -> Path:
    if not SAFE_NAME.fullmatch(name) or name.startswith("."):
        raise HTTPException(status_code=404, detail="Not found")
    path = (parent / name).resolve()
    if path.parent != parent.resolve() or not path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    return path


app = create_app()
