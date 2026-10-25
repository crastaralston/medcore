"""Loads a PDF or image and rebuilds its text as lines, keeping table columns apart.

Columns are separated by two spaces, so 'Platelet Count  85,000  /cumm' stays one row.
PDFs are read from their text layer; images go through Tesseract OCR.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import pymupdf
from PIL import Image, UnidentifiedImageError

from ..models import SourceFile

MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_PAGES = 5
IMAGE_TYPES = {"PNG", "JPEG", "WEBP", "TIFF", "BMP"}


class UnreadableFile(ValueError):
    """The file is not a readable PDF or image."""


@dataclass
class _Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def area(self) -> float:
        return max(self.x1 - self.x0, 0) * max(self.y1 - self.y0, 0)

    def overlap(self, other: _Word) -> float:
        """Share of the smaller word's box covered by the other word."""
        w = min(self.x1, other.x1) - max(self.x0, other.x0)
        h = min(self.y1, other.y1) - max(self.y0, other.y0)
        if w <= 0 or h <= 0:
            return 0.0
        return (w * h) / max(min(self.area, other.area), 1e-6)


def _drop_overprinted(words: list[_Word]) -> tuple[list[_Word], list[str]]:
    """Where a later word sits on top of an earlier one, keep the later (visible) word."""
    kept: list[_Word] = []
    events: list[str] = []
    for w in words:
        clash = next((k for k in kept if k.text != w.text and k.overlap(w) > 0.5), None)
        if clash is not None:
            events.append(f"'{w.text}' is printed on top of '{clash.text}'")
            kept.remove(clash)
        kept.append(w)
    return kept, events


def _to_lines(words: list[_Word]) -> list[str]:
    """Group words into lines by vertical position; a wide gap becomes a column break."""
    if not words:
        return []
    heights = sorted(w.y1 - w.y0 for w in words)
    h = heights[len(heights) // 2] or 1.0
    rows: list[list[_Word]] = []
    for w in sorted(words, key=lambda w: ((w.y0 + w.y1) / 2, w.x0)):
        mid = (w.y0 + w.y1) / 2
        if rows and abs(mid - _mid(rows[-1])) < h * 0.45:
            rows[-1].append(w)
        else:
            rows.append([w])
    lines = []
    for row in rows:
        row.sort(key=lambda w: w.x0)
        parts = [row[0].text]
        for prev, cur in zip(row, row[1:]):
            parts.append("  " if cur.x0 - prev.x1 > h * 0.8 else " ")
            parts.append(cur.text)
        lines.append("".join(parts))
    return lines


def _mid(row: list[_Word]) -> float:
    return sum((w.y0 + w.y1) / 2 for w in row) / len(row)


def _read_pdf(src: SourceFile) -> None:
    try:
        doc = pymupdf.open(stream=src.data, filetype="pdf")
    except Exception as exc:  # pymupdf raises several types for damaged files
        raise UnreadableFile(f"{src.name}: not a readable PDF ({exc})") from exc
    with doc:
        if doc.needs_pass:
            raise UnreadableFile(f"{src.name}: the PDF is password-protected")
        for page in list(doc)[:MAX_PAGES]:
            words = [_Word(t[4], t[0], t[1], t[2], t[3]) for t in page.get_text("words")]
            words, events = _drop_overprinted(words)
            src.overlapping_text.extend(events)
            src.lines.extend(_to_lines(words))
        pix = doc[0].get_pixmap(dpi=72)
        src.preview = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def _read_image(src: SourceFile, image: Image.Image) -> None:
    import pytesseract  # imported here so PDF-only use needs no Tesseract binary

    image = image.convert("RGB")
    src.preview = image.copy()
    src.preview.thumbnail((620, 880))
    try:
        data = pytesseract.image_to_data(image, config="--psm 4", output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractNotFoundError as exc:
        raise UnreadableFile("Tesseract OCR is not installed, so image files cannot be read") from exc
    words = [
        _Word(text, left, top, left + width, top + height)
        for text, left, top, width, height, conf in zip(
            data["text"], data["left"], data["top"], data["width"], data["height"], data["conf"])
        if text.strip() and float(conf) > 30
    ]
    src.lines.extend(_to_lines(words))


def load(name: str, data: bytes) -> SourceFile:
    if len(data) == 0:
        raise UnreadableFile(f"{name}: the file is empty")
    if len(data) > MAX_FILE_BYTES:
        raise UnreadableFile(f"{name}: larger than {MAX_FILE_BYTES // (1024 * 1024)} MB")
    if data[:5] == b"%PDF-":
        src = SourceFile(name=name, kind="pdf", data=data)
        _read_pdf(src)
        return src
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise UnreadableFile(f"{name}: not a PDF or a supported image") from exc
    if image.format not in IMAGE_TYPES:
        raise UnreadableFile(f"{name}: image type {image.format} is not supported")
    src = SourceFile(name=name, kind="image", data=data)
    _read_image(src, image)
    return src
