"""The registry of issuers and the hash-chained public log of every seal."""

from __future__ import annotations

import hashlib
import json
import re
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select

from ..db import Issuer, LedgerEntry, Store
from .crypto import fingerprint

GENESIS = "0" * 64
KINDS = ("hospital", "lab", "pharmacy")
BURST_WINDOW = timedelta(minutes=60)
BURST_LIMIT = 25  # seals by one issuer within the window that count as unusual


class RegistryError(ValueError):
    pass


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80] or "issuer"


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def entry_hash(e: LedgerEntry) -> str:
    fields = [e.seq, e.kind, e.doc_id, e.issuer_id, e.doc_type, e.stay_id,
              _utc(e.created_at).isoformat(), e.payload_hash, e.reason, e.prev_hash]
    return hashlib.sha256(json.dumps(fields, separators=(",", ":")).encode()).hexdigest()


def issuer_json(i: Issuer, sealed: int = 0) -> dict:
    return {"id": i.id, "name": i.name, "kind": i.kind, "address": i.address, "status": i.status,
            "key_fingerprint": fingerprint(i.public_key), "created_at": _utc(i.created_at).isoformat(),
            "documents_sealed": sealed}


def entry_json(e: LedgerEntry) -> dict:
    return {"seq": e.seq, "kind": e.kind, "doc_id": e.doc_id, "issuer_id": e.issuer_id, "doc_type": e.doc_type,
            "stay_id": e.stay_id, "created_at": _utc(e.created_at).isoformat(), "reason": e.reason,
            "payload_hash": e.payload_hash, "entry_hash": e.entry_hash}


class Registry:
    def __init__(self, store: Store):
        self.store = store
        self._lock = threading.Lock()  # keeps the chain in order within one server process

    # Issuers

    def issuers(self) -> list[Issuer]:
        with self.store.session() as s:
            return list(s.scalars(select(Issuer).order_by(Issuer.kind, Issuer.name)))

    def issuer(self, issuer_id: str) -> Issuer | None:
        with self.store.session() as s:
            return s.get(Issuer, issuer_id)

    def register(self, name: str, kind: str, address: str, public_key: str, issuer_id: str | None = None) -> Issuer:
        name, address = name.strip(), address.strip()
        if not name:
            raise RegistryError("Give the hospital, lab or pharmacy a name.")
        if kind not in KINDS:
            raise RegistryError(f"Kind must be one of: {', '.join(KINDS)}.")
        issuer_id = issuer_id or slugify(name)
        with self.store.session() as s, s.begin():
            if s.get(Issuer, issuer_id) is not None:
                raise RegistryError(f"'{name}' is already registered.")
            issuer = Issuer(id=issuer_id, name=name, kind=kind, address=address, public_key=public_key,
                            status="active", created_at=datetime.now(timezone.utc))
            s.add(issuer)
        return issuer

    def set_status(self, issuer_id: str, status: str) -> Issuer:
        if status not in ("active", "suspended"):
            raise RegistryError("Status must be 'active' or 'suspended'.")
        with self.store.session() as s, s.begin():
            issuer = s.get(Issuer, issuer_id)
            if issuer is None:
                raise RegistryError("No such issuer.")
            issuer.status = status
        return issuer

    def sealed_counts(self) -> dict[str, int]:
        with self.store.session() as s:
            rows = s.execute(select(LedgerEntry.issuer_id, func.count()).where(LedgerEntry.kind == "seal")
                             .group_by(LedgerEntry.issuer_id))
            return {issuer_id: n for issuer_id, n in rows}

    # The public log

    def append(self, kind: str, doc_id: str, issuer_id: str, doc_type: str, stay_id: str | None,
               payload_hash: str, reason: str | None = None, at: datetime | None = None) -> LedgerEntry:
        with self._lock, self.store.session() as s, s.begin():
            last = s.scalars(select(LedgerEntry).order_by(LedgerEntry.seq.desc()).limit(1)).first()
            entry = LedgerEntry(seq=(last.seq + 1) if last else 1, kind=kind, doc_id=doc_id, issuer_id=issuer_id,
                                doc_type=doc_type, stay_id=stay_id, created_at=at or datetime.now(timezone.utc),
                                payload_hash=payload_hash, reason=reason,
                                prev_hash=last.entry_hash if last else GENESIS, entry_hash="")
            entry.entry_hash = entry_hash(entry)
            s.add(entry)
        return entry

    def entries(self, limit: int = 100) -> list[LedgerEntry]:
        with self.store.session() as s:
            return list(s.scalars(select(LedgerEntry).order_by(LedgerEntry.seq.desc()).limit(limit)))

    def find(self, doc_id: str, kind: str = "seal") -> LedgerEntry | None:
        with self.store.session() as s:
            return s.scalars(select(LedgerEntry).where(LedgerEntry.doc_id == doc_id, LedgerEntry.kind == kind)
                             .order_by(LedgerEntry.seq)).first()

    def revoke(self, doc_id: str, reason: str) -> LedgerEntry:
        seal = self.find(doc_id)
        if seal is None:
            raise RegistryError("No seal with that ID is in the log.")
        if self.find(doc_id, "revoke") is not None:
            raise RegistryError("That seal is already revoked.")
        return self.append("revoke", doc_id, seal.issuer_id, seal.doc_type, seal.stay_id, seal.payload_hash,
                           reason=(reason.strip() or "Revoked by issuer")[:300])

    def verify_chain(self) -> tuple[bool, list[int]]:
        """Recompute every hash. Returns (intact, sequence numbers where the chain breaks)."""
        broken: list[int] = []
        prev, expected_seq = GENESIS, 1
        with self.store.session() as s:
            for e in s.scalars(select(LedgerEntry).order_by(LedgerEntry.seq)):
                if e.seq != expected_seq or e.prev_hash != prev or entry_hash(e) != e.entry_hash:
                    broken.append(e.seq)
                prev, expected_seq = e.entry_hash, e.seq + 1
        return not broken, broken

    def alerts(self) -> list[dict]:
        """Issuing patterns worth a human look. This version has one rule: bursts."""
        by_issuer: dict[str, list[datetime]] = defaultdict(list)
        with self.store.session() as s:
            for issuer_id, at in s.execute(select(LedgerEntry.issuer_id, LedgerEntry.created_at)
                                           .where(LedgerEntry.kind == "seal").order_by(LedgerEntry.created_at)):
                by_issuer[issuer_id].append(_utc(at))
        names = {i.id: i.name for i in self.issuers()}
        out = []
        for issuer_id, times in by_issuer.items():
            start = 0
            for end, t in enumerate(times):
                while t - times[start] > BURST_WINDOW:
                    start += 1
                if end - start + 1 > BURST_LIMIT:
                    out.append({"rule": "burst", "issuer_id": issuer_id, "issuer": names.get(issuer_id, issuer_id),
                                "title": "Unusually many documents sealed in one hour",
                                "detail": f"{end - start + 1} documents sealed between {times[start]:%d %b %H:%M} "
                                          f"and {t:%H:%M} UTC; more than {BURST_LIMIT} in an hour is unusual."})
                    break
        return out


def export_log(registry: Registry) -> list[dict]:
    """Log entries in order, for shipping a demo history with the demo pack."""
    return [{"kind": e.kind, "doc_id": e.doc_id, "issuer_id": e.issuer_id, "doc_type": e.doc_type,
             "stay_id": e.stay_id, "created_at": _utc(e.created_at).isoformat(), "payload_hash": e.payload_hash,
             "reason": e.reason} for e in reversed(registry.entries(limit=100000))]


def seed_from(registry: Registry, folder: Path) -> None:
    """Register the demo issuers and replay the demo log, skipping anything already present."""
    from .crypto import KeyStore, public_pem

    issuers_file = folder / "issuers.json"
    if not issuers_file.exists():
        return
    keys = KeyStore(folder)
    for item in json.loads(issuers_file.read_text()):
        key = keys.load(item["id"])
        if registry.issuer(item["id"]) is None and key is not None:
            registry.register(item["name"], item["kind"], item["address"], public_pem(key), issuer_id=item["id"])
    log_file = folder / "log.json"
    if log_file.exists():
        for e in json.loads(log_file.read_text()):
            if registry.find(e["doc_id"], e["kind"]) is None:
                registry.append(e["kind"], e["doc_id"], e["issuer_id"], e["doc_type"], e["stay_id"], e["payload_hash"],
                                reason=e.get("reason"), at=datetime.fromisoformat(e["created_at"]))
