"""Sealing a document, and checking a seal against the page it is printed on."""

from __future__ import annotations

import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from ..models import DOC_TYPE_LABELS, ExtractedDoc, Flag, SourceFile
from ..reading.extract import extract
from ..reading.loader import UnreadableFile, load
from . import crypto, qr
from .facts import FieldCheck, compare, facts, text_fingerprint
from .registry import Registry, entry_json, issuer_json

ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I, so IDs read clearly aloud


class SealError(ValueError):
    pass


def new_doc_id() -> str:
    return "".join(secrets.choice(ID_ALPHABET) for _ in range(12))


@dataclass
class SealResult:
    doc_id: str
    token: str
    pdf: bytes
    payload: dict
    doc: ExtractedDoc


def seal_pdf(registry: Registry, keys: crypto.KeyStore, issuer_id: str, file_name: str, data: bytes,
             stay_id: str | None = None) -> SealResult:
    """Read the document, sign its key facts, stamp the QR code and log the seal."""
    issuer = registry.issuer(issuer_id)
    if issuer is None:
        raise SealError("That hospital or lab is not registered.")
    if issuer.status != "active":
        raise SealError(f"{issuer.name} is suspended and cannot seal documents.")
    key = keys.load(issuer_id)
    if key is None:
        raise SealError(f"The signing key for {issuer.name} is not installed on this machine.")
    if crypto.public_pem(key) != issuer.public_key:
        raise SealError(f"The installed key for {issuer.name} does not match its registered key.")
    try:
        src = load(file_name, data)
    except UnreadableFile as exc:
        raise SealError(str(exc)) from exc
    if src.kind != "pdf":
        raise SealError("Only PDF documents can be sealed in this version.")
    if qr.find_tokens(src):
        raise SealError("This document already carries a QR code; it may already be sealed.")
    doc = extract(src)
    if doc.doc_type == "unknown":
        raise SealError("Could not tell what kind of document this is, so it cannot be sealed.")

    stay = (stay_id or "").strip()[:80] or None
    doc_id = new_doc_id()
    payload = {"v": 1, "id": doc_id, "iss": issuer_id, "typ": doc.doc_type,
               "iat": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "stay": stay,
               "f": facts(doc), "fp": text_fingerprint(src.lines)}
    token = crypto.sign_token(payload, key)
    sealed = qr.stamp(data, token, doc_id)
    registry.append("seal", doc_id, issuer_id, doc.doc_type, stay, crypto.payload_hash(crypto.canonical(payload)))
    return SealResult(doc_id, token, sealed, payload, doc)


STATUS_TITLES = {
    "genuine": "Genuine",
    "altered": "Altered after sealing",
    "revoked": "Seal was revoked",
    "unlogged": "Seal is not in the public log",
    "bad_signature": "Seal signature is invalid",
    "unknown_issuer": "Sealed by an unregistered issuer",
    "unreadable": "QR code is not a MedCore seal",
    "no_seal": "No seal on this document",
}


@dataclass
class SealCheck:
    status: str
    title: str
    detail: str
    doc_id: str | None = None
    issuer: dict | None = None
    sealed_at: str | None = None
    stay_id: str | None = None
    doc_type: str | None = None
    fields: list[FieldCheck] = field(default_factory=list)
    text_matches: bool | None = None
    log_entry: dict | None = None
    revocation: dict | None = None

    def to_json(self) -> dict:
        return asdict(self)


def check_seal(registry: Registry, src: SourceFile, doc: ExtractedDoc) -> SealCheck:
    tokens = qr.find_tokens(src)
    if not tokens:
        return SealCheck("no_seal", STATUS_TITLES["no_seal"],
                         "This document has no QR seal, so only the three content checks apply.")
    token = next((t for t in tokens if t.startswith(crypto.PREFIX + ".")), tokens[0])
    try:
        payload, body, signature = crypto.parse_token(token)
    except crypto.TokenError as exc:
        return SealCheck("unreadable", STATUS_TITLES["unreadable"], f"A QR code was found, but {exc}.")

    doc_id = str(payload.get("id", ""))
    base = dict(doc_id=doc_id, sealed_at=payload.get("iat"), stay_id=payload.get("stay"), doc_type=payload.get("typ"))
    issuer = registry.issuer(str(payload.get("iss", "")))
    if issuer is None:
        return SealCheck("unknown_issuer", STATUS_TITLES["unknown_issuer"],
                         f"The seal claims to come from '{payload.get('iss')}', which is not in the registry. "
                         "Anyone can print a QR code; only registered issuers can make a valid seal.", **base)
    base["issuer"] = issuer_json(issuer)
    if not crypto.signature_valid(issuer.public_key, body, signature):
        return SealCheck("bad_signature", STATUS_TITLES["bad_signature"],
                         f"The QR code was not signed with {issuer.name}'s key, or its contents were changed.", **base)

    logged = registry.find(doc_id)
    if logged is None or logged.payload_hash != crypto.payload_hash(body):
        return SealCheck("unlogged", STATUS_TITLES["unlogged"],
                         f"The signature is {issuer.name}'s, but this seal was never recorded in the public log. "
                         "Every genuine seal is logged when it is made, so the signing key may have been stolen.",
                         **base)
    base["log_entry"] = entry_json(logged)
    revoked = registry.find(doc_id, "revoke")
    if revoked is not None:
        return SealCheck("revoked", STATUS_TITLES["revoked"],
                         f"{issuer.name} revoked this seal: {revoked.reason}", revocation=entry_json(revoked), **base)

    checks = compare(payload.get("f", {}), doc)
    text_matches = (text_fingerprint(src.lines) == payload.get("fp")) if src.kind == "pdf" else None
    different = [c for c in checks if c.status == "different"]
    type_changed = payload.get("typ") != doc.doc_type
    if different or type_changed or text_matches is False:
        if different:
            detail = "; ".join(f"{c.label}: signed '{c.signed}', printed '{c.printed}'" for c in different)
        elif type_changed:
            detail = f"Sealed as a {DOC_TYPE_LABELS.get(str(payload.get('typ')), 'document').lower()}, " \
                     f"but this page reads as a {DOC_TYPE_LABELS[doc.doc_type].lower()}."
        else:
            detail = "The key facts match, but other text on the page was changed after sealing."
        return SealCheck("altered", STATUS_TITLES["altered"], detail, fields=checks, text_matches=text_matches,
                         **base)
    sealed_on = (payload.get("iat") or "")[:10]
    return SealCheck("genuine", STATUS_TITLES["genuine"],
                     f"Sealed by {issuer.name} on {sealed_on}. Every signed fact matches the printed page"
                     + (", and so does the rest of the text." if text_matches else "."),
                     fields=checks, text_matches=text_matches, **base)


def verify_upload(registry: Registry, file_name: str, data: bytes) -> tuple[SealCheck, ExtractedDoc, SourceFile]:
    src = load(file_name, data)
    doc = extract(src)
    return check_seal(registry, src, doc), doc, src


SEVERE = {"altered", "revoked", "unlogged", "bad_signature", "unknown_issuer"}


def seal_flags(docs: list[ExtractedDoc], checks: list[SealCheck]) -> list[Flag]:
    """Turn seal results into claim-check flags: problems go to check 1, mixed stays to check 2."""
    flags: list[Flag] = []
    for d, c in zip(docs, checks):
        if c.status in SEVERE:
            evidence = [f"{f.label}: signed {f.signed}, printed {f.printed}" for f in c.fields if f.status == "different"]
            if c.doc_id:
                evidence.append(f"Seal ID {qr.display_id(c.doc_id)}")
            flags.append(Flag(1, f"seal_{c.status}", "high", c.title, c.detail, [d.file_name], evidence))
        elif c.status == "unreadable":
            flags.append(Flag(1, "seal_unreadable", "medium", c.title, c.detail, [d.file_name], []))

    stays: dict[str, list[str]] = {}
    for d, c in zip(docs, checks):
        if c.status == "genuine" and c.stay_id:
            stays.setdefault(c.stay_id, []).append(d.file_name)
    if len(stays) > 1:
        parts = "; ".join(f"{stay}: {', '.join(files)}" for stay, files in stays.items())
        flags.append(Flag(2, "seal_stay_mismatch", "high", "Sealed documents come from different hospital stays",
                          f"Each document's seal names the stay it belongs to, and they do not agree. {parts}.",
                          [f for files in stays.values() for f in files], list(stays)))
    return flags
