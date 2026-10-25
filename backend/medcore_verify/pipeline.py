"""Runs one claim file through the reader and the three checkers."""

from __future__ import annotations

import re
import time
from pathlib import PurePath

from .checks import agreement, forensics, medical
from .models import Report, SourceFile, decide_verdict
from .reading.extract import extract
from .reading.loader import UnreadableFile, load
from .seal.registry import Registry
from .seal.service import check_seal, seal_flags

MAX_FILES = 12
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


class InvalidClaim(ValueError):
    """The upload cannot be checked as a claim file."""


def _unique_names(names: list[str]) -> list[str]:
    """Safe, unique file names: no folders, no odd characters, no clashes."""
    seen: dict[str, int] = {}
    out = []
    for raw in names:
        name = re.sub(r"[^\w\-. ()]", "_", PurePath(raw.replace("\\", "/")).name).lstrip(".")[:120] or "document"
        if name in seen:
            seen[name] += 1
            stem, dot, ext = name.rpartition(".")
            name = f"{stem}-{seen[name]}.{ext}" if dot else f"{name}-{seen[name]}"
        else:
            seen[name] = 0
        out.append(name)
    return out


def analyze(files: list[tuple[str, bytes]], registry: Registry | None = None) -> tuple[Report, list[SourceFile]]:
    """Check one claim. `files` is a list of (file name, bytes).

    With a `registry`, every document's QR seal is also checked against the printed page.
    """
    if not files:
        raise InvalidClaim("Upload at least one document.")
    if len(files) > MAX_FILES:
        raise InvalidClaim(f"A claim can have at most {MAX_FILES} documents.")
    start = time.perf_counter()
    names = _unique_names([n for n, _ in files])
    try:
        sources = [load(name, data) for name, (_, data) in zip(names, files)]
    except UnreadableFile as exc:
        raise InvalidClaim(str(exc)) from exc
    docs = [extract(s) for s in sources]

    notes = [f"Could not tell what kind of document {d.file_name} is, so it was only checked for editing signs."
             for d in docs if d.doc_type == "unknown"]
    flags = []
    if registry is not None:
        seals = [check_seal(registry, s, d) for s, d in zip(sources, docs)]
        for d, c in zip(docs, seals):
            d.seal = c.to_json()
        flags += seal_flags(docs, seals)
    for checker_flags, checker_notes in (forensics.check(sources), agreement.check(docs), medical.check(docs)):
        flags += checker_flags
        notes += checker_notes
    flags.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.checker))
    report = Report(decide_verdict(flags), flags, docs, time.perf_counter() - start, notes)
    return report, sources
