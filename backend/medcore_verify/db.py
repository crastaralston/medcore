"""Stores every check: SQLite by default, PostgreSQL by setting DATABASE_URL."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class ClaimCheck(Base):
    __tablename__ = "claim_checks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    label: Mapped[str] = mapped_column(String(200))
    verdict: Mapped[str] = mapped_column(String(20))
    flag_count: Mapped[int] = mapped_column(Integer)
    patient_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    file_names: Mapped[str] = mapped_column(Text)  # JSON list
    report_json: Mapped[str] = mapped_column(Text)
    truth_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # only for demo samples

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "label": self.label,
            "verdict": self.verdict,
            "flag_count": self.flag_count,
            "patient_name": self.patient_name,
            "file_names": json.loads(self.file_names),
        }

    def full(self) -> dict[str, Any]:
        return self.summary() | {
            "report": json.loads(self.report_json),
            "truth": json.loads(self.truth_json) if self.truth_json else None,
        }


class Issuer(Base):
    """A registered hospital, lab or pharmacy and the public key that checks its seals."""

    __tablename__ = "issuers"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))  # hospital, lab or pharmacy
    address: Mapped[str] = mapped_column(String(300))
    public_key: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active or suspended
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LedgerEntry(Base):
    """One line of the public log. Holds no patient data: only IDs, types and hashes.
    Each entry's hash covers the previous entry's hash, so changing or deleting any
    entry breaks every hash after it."""

    __tablename__ = "ledger"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))  # seal or revoke
    doc_id: Mapped[str] = mapped_column(String(32), index=True)
    issuer_id: Mapped[str] = mapped_column(String(80), index=True)
    doc_type: Mapped[str] = mapped_column(String(40))
    stay_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload_hash: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    prev_hash: Mapped[str] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64))


class Store:
    def __init__(self, url: str):
        args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, connect_args=args)
        Base.metadata.create_all(self.engine)
        self._session = sessionmaker(self.engine, expire_on_commit=False)

    def session(self) -> Session:
        return self._session()

    def add(self, check: ClaimCheck) -> None:
        with self.session() as s, s.begin():
            s.add(check)

    def get(self, check_id: str) -> ClaimCheck | None:
        with self.session() as s:
            return s.get(ClaimCheck, check_id)

    def recent(self, limit: int = 50) -> list[ClaimCheck]:
        with self.session() as s:
            return list(s.scalars(select(ClaimCheck).order_by(ClaimCheck.created_at.desc()).limit(limit)))

    def delete(self, check_id: str) -> bool:
        with self.session() as s, s.begin():
            check = s.get(ClaimCheck, check_id)
            if check is None:
                return False
            s.delete(check)
            return True


def now() -> datetime:
    return datetime.now(timezone.utc)
