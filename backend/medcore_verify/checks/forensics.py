"""Checker 1: signs that a file was edited after it was made.

This version inspects PDFs only. Image forensics (white-out patches, pasted regions,
font mismatches in scans) is future scope; image files are reported as not checked.
"""

from __future__ import annotations

from datetime import datetime

import pymupdf

from ..models import Flag, SourceFile

EDIT_TOOLS = ("ilovepdf", "sejda", "pdfescape", "smallpdf", "pdf-xchange editor", "pdffiller", "dochub",
              "foxit phantompdf", "nitro pro", "canva", "photoshop", "gimp", "inkscape", "pdf candy")


def _pdf_date(value: str | None) -> datetime | None:
    if not value or not value.startswith("D:") or len(value) < 16:
        return None
    try:
        return datetime.strptime(value[2:16], "%Y%m%d%H%M%S")
    except ValueError:
        return None


def _white_boxes_over_text(doc: pymupdf.Document) -> list[str]:
    """Filled white rectangles drawn on top of words. Returns the hidden words."""
    hidden: list[str] = []
    for page in list(doc)[:5]:
        words = page.get_text("words")
        for drawing in page.get_drawings():
            fill = drawing.get("fill")
            if not fill or min(fill) < 0.95:
                continue
            rect = drawing["rect"]
            for w in words:
                box = pymupdf.Rect(w[:4])
                inter = box & rect
                if not inter.is_empty and inter.get_area() > 0.6 * box.get_area():
                    hidden.append(w[4])
    return hidden


def _check_pdf(src: SourceFile) -> list[Flag]:
    flags: list[Flag] = []
    doc = pymupdf.open(stream=src.data, filetype="pdf")
    with doc:
        hidden = _white_boxes_over_text(doc)
        if src.overlapping_text or hidden:
            evidence = list(src.overlapping_text[:3])
            if hidden:
                evidence.append("Covered by a white box: " + ", ".join(f"'{h}'" for h in hidden[:5]))
            flags.append(Flag(
                1, "pdf_overprint", "high", "Text painted over inside the PDF",
                "A value was covered and new text typed on top. The original text is still in the file.",
                [src.name], evidence))

        saves = src.data.count(b"%%EOF")
        expected = 2 if doc.is_fast_webaccess else 1
        if saves > expected:
            signed = doc.get_sigflags() > 0
            flags.append(Flag(
                1, "pdf_resaved", "low" if signed else "medium", "PDF was saved again after it was made",
                f"The file has {saves - expected} extra save layer(s) added on top of the original."
                + (" It carries a digital signature, which can explain this." if signed else ""),
                [src.name], [f"{saves} end-of-file markers"]))

        meta = doc.metadata or {}
        tools = " ".join(filter(None, (meta.get("producer"), meta.get("creator")))).lower()
        tool = next((t for t in EDIT_TOOLS if t in tools), None)
        if tool:
            flags.append(Flag(
                1, "pdf_edit_tool", "medium", "PDF last written by an editing tool",
                "Hospital and lab systems do not normally produce files with this tool.",
                [src.name], [f"Producer: {meta.get('producer')}", f"Creator: {meta.get('creator')}"]))

        created, modified = _pdf_date(meta.get("creationDate")), _pdf_date(meta.get("modDate"))
        if created and modified and (modified - created).days >= 1:
            flags.append(Flag(
                1, "pdf_modified_later", "low", "PDF modified after it was created",
                f"Modified {(modified - created).days} day(s) after creation.",
                [src.name], [f"Created {created:%d %b %Y}, modified {modified:%d %b %Y}"]))
    return flags


def check(sources: list[SourceFile]) -> tuple[list[Flag], list[str]]:
    flags: list[Flag] = []
    notes: list[str] = []
    images = [s.name for s in sources if s.kind == "image"]
    for src in sources:
        if src.kind == "pdf":
            flags += _check_pdf(src)
    if images:
        notes.append("Editing signs were not checked for image files yet (future scope): " + ", ".join(images))
    return flags, notes
