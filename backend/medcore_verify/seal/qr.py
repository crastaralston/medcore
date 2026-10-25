"""Drawing the QR code onto a PDF page, and finding it again in a PDF or a photo."""

from __future__ import annotations

import io

import cv2
import numpy as np
import pymupdf
import qrcode
import zxingcpp
from PIL import Image
from qrcode.constants import ERROR_CORRECT_L

from ..models import SourceFile

QR_SIZE = 96  # points, about 3.4 cm on paper
MARGIN = 36


def qr_png(token: str, box: int = 8) -> bytes:
    code = qrcode.QRCode(error_correction=ERROR_CORRECT_L, box_size=box, border=2)
    code.add_data(token)
    code.make(fit=True)
    buf = io.BytesIO()
    code.make_image(fill_color="black", back_color="white").save(buf, format="PNG")
    return buf.getvalue()


def display_id(doc_id: str) -> str:
    return "-".join(doc_id[i:i + 4] for i in range(0, len(doc_id), 4))


def stamp(pdf: bytes, token: str, doc_id: str) -> bytes:
    """Put the QR code in the bottom-right corner of page 1, with a short caption."""
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    with doc:
        page = doc[0]
        w, h = page.rect.width, page.rect.height
        rect = pymupdf.Rect(w - MARGIN - QR_SIZE, h - MARGIN - QR_SIZE - 10, w - MARGIN, h - MARGIN - 10)
        page.insert_image(rect, stream=qr_png(token))
        page.insert_text((rect.x0 - 2, rect.y1 + 8), f"MedCore Seal {display_id(doc_id)}", fontsize=6,
                         fontname="helv", color=(0.25, 0.25, 0.25))
        page.insert_text((rect.x0 - 2, rect.y0 - 3), "Scan to verify", fontsize=6, fontname="helv",
                         color=(0.25, 0.25, 0.25))
        meta = dict(doc.metadata)
        meta["producer"] = "MedCore Seal 0.1"
        doc.set_metadata(meta)
        return doc.tobytes(garbage=3, deflate=True)


def _decode(image: np.ndarray) -> list[str]:
    """zxing-cpp first (it decodes far more reliably), OpenCV's detector as a fallback."""
    out = [r.text for r in zxingcpp.read_barcodes(image, formats=zxingcpp.BarcodeFormat.QRCode) if r.text]
    if out:
        return out
    detector = cv2.QRCodeDetector()
    found, texts, _, _ = detector.detectAndDecodeMulti(image)
    out = [t for t in texts if t] if found else []
    if not out:
        text, _, _ = detector.detectAndDecode(image)
        if text:
            out.append(text)
    return out


def find_tokens(src: SourceFile) -> list[str]:
    """Every QR text on the first page. PDFs are rendered at print resolution first."""
    if src.kind == "pdf":
        return _pdf_tokens(src.data)
    for attempt in _variants(np.array(Image.open(io.BytesIO(src.data)).convert("L"))):
        tokens = _decode(attempt)
        if tokens:
            return tokens
    return []


def _gray(pix: pymupdf.Pixmap) -> np.ndarray:
    if pix.n - pix.alpha != 1:
        pix = pymupdf.Pixmap(pymupdf.csGRAY, pix)
    if pix.alpha:
        pix = pymupdf.Pixmap(pix, 0)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)


def _pdf_tokens(data: bytes) -> list[str]:
    doc = pymupdf.open(stream=data, filetype="pdf")
    with doc:
        page = doc[0]
        # 1. QR codes are usually embedded images: read them at full resolution.
        for xref, *_ in page.get_images(full=True):
            try:
                image = _gray(pymupdf.Pixmap(doc, xref))
            except (RuntimeError, ValueError):
                continue
            if min(image.shape) < 21:
                continue
            for attempt in (image, cv2.resize(image, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST)):
                tokens = _decode(attempt)
                if tokens:
                    return tokens
        # 2. Otherwise the code may be drawn as shapes: render the page at print resolution.
        if not page.get_drawings():
            return []
        return _decode(_gray(page.get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)))


def _variants(image: np.ndarray):
    """The image as given, then versions that help the detector with scans and photos."""
    yield image
    _, bw = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    yield bw
    longest = max(image.shape)
    if longest < 3600:  # small or medium scans: enlarge so each QR module spans more pixels
        big = cv2.resize(image, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        _, big_bw = cv2.threshold(big, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        yield big_bw
    if longest > 2400:  # large phone photos: shrink to cut noise
        scale = 2400 / longest
        yield cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
