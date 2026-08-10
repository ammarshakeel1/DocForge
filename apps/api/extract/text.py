import io
import logging
from dataclasses import dataclass

import pdfplumber
from pypdf import PdfReader

logger = logging.getLogger(__name__)

MIN_TEXT_CHARS = 40


@dataclass
class TextExtractionResult:
    text: str
    method: str
    error: str | None = None


def extract_text_from_pdf(pdf_bytes: bytes) -> TextExtractionResult:
    """Extract text; OCR is optional and never raises to the caller."""
    text = _extract_with_pdfplumber(pdf_bytes)
    if _has_enough_text(text):
        return TextExtractionResult(text=text.strip(), method="pdfplumber")

    text = _extract_with_pypdf(pdf_bytes)
    if _has_enough_text(text):
        return TextExtractionResult(text=text.strip(), method="pypdf")

    ocr = _extract_with_ocr(pdf_bytes)
    if _has_enough_text(ocr.text):
        return TextExtractionResult(text=ocr.text.strip(), method="ocr")

    if ocr.error:
        error = (
            "No selectable text layer found, and OCR is unavailable or failed: "
            f"{ocr.error}. Install Tesseract for scanned PDFs, or upload a text PDF."
        )
    else:
        error = (
            "No selectable text layer found and OCR returned empty text. "
            "Install Tesseract for scanned PDFs, or upload a text PDF."
        )
    return TextExtractionResult(text="", method="none", error=error)


def _has_enough_text(text: str) -> bool:
    return len((text or "").strip()) >= MIN_TEXT_CHARS


def _extract_with_pdfplumber(pdf_bytes: bytes) -> str:
    chunks: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    chunks.append(page_text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("pdfplumber extraction failed: %s", exc)
    return "\n".join(chunks)


def _extract_with_pypdf(pdf_bytes: bytes) -> str:
    chunks: list[str] = []
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                chunks.append(page_text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("pypdf extraction failed: %s", exc)
    return "\n".join(chunks)


@dataclass
class _OcrAttempt:
    text: str
    error: str | None = None


def _extract_with_ocr(pdf_bytes: bytes) -> _OcrAttempt:
    """OCR fallback for scanned PDFs. Optional — failures return an error string."""
    try:
        import pytesseract
        import pypdfium2 as pdfium
        from PIL import Image
    except ImportError as exc:
        return _OcrAttempt(text="", error=f"OCR Python deps missing ({exc})")

    try:
        # Probe tesseract binary early for a clear message.
        pytesseract.get_tesseract_version()
    except Exception as exc:  # noqa: BLE001
        return _OcrAttempt(
            text="",
            error=f"Tesseract not installed or not on PATH ({exc})",
        )

    chunks: list[str] = []
    try:
        pdf = pdfium.PdfDocument(pdf_bytes)
        for index in range(len(pdf)):
            page = pdf[index]
            bitmap = page.render(scale=2)
            pil_image = bitmap.to_pil()
            if not isinstance(pil_image, Image.Image):
                pil_image = Image.fromarray(pil_image)
            chunks.append(pytesseract.image_to_string(pil_image))
    except Exception as exc:  # noqa: BLE001
        logger.warning("OCR extraction failed: %s", exc)
        return _OcrAttempt(text="", error=str(exc))

    return _OcrAttempt(text="\n".join(chunks))
