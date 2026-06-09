from __future__ import annotations

import io
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document as DocxDocument
from PIL import Image as PILImage
from pypdf import PdfReader

from app.loaders.errors import LoaderError

MIN_IMAGE_BYTES = 1024  # base size filter; stricter content checks below

IMAGE_FILE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})

def _has_pdfimages() -> bool:
    """Check if pdfimages (from poppler-utils) is available for superior embedded image extraction."""
    return shutil.which("pdfimages") is not None


def _extract_images_pdfimages(pdf_path: Path, output_dir: Path, prefix: str = "img") -> list[Path]:
    """
    Extract embedded images using pdfimages in original format where possible.
    Returns list of extracted file paths. Superior quality to many pure-Python extractors.
    """
    if not _has_pdfimages():
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        # -all: try original format; fallback to png
        subprocess.run(
            ["pdfimages", "-all", "-png", str(pdf_path), str(output_dir / prefix)],
            capture_output=True,
            timeout=60,
            check=True,
        )
        # Collect created files
        extracted = sorted(output_dir.glob(f"{prefix}-*"))
        return [p for p in extracted if p.is_file()]
    except Exception:
        return []


def _is_meaningful_image(data: bytes, *, strict: bool = True) -> bool:
    """Heuristic to decide if an embedded PDF/DOCX image is real content worth Vision-OCR.

    - strict=True (default, used on pages that have vector text): very strict filter to avoid
      page background textures, watermarks, subtle gradients that are common in "designed" text PDFs.
    - strict=False (used on pages without extractable text layer): more lenient so that scanned
      documents, image-based slides, or full-page text-as-image are still offered for OCR.

    Real screenshots, diagrams, photos, figures, and page-filling content images should pass.
    """
    if len(data) < MIN_IMAGE_BYTES:
        return False
    try:
        with PILImage.open(io.BytesIO(data)) as im:
            w, h = im.size
            if w < 120 or h < 120:
                return False

            # Quick low-info test
            gray = im.convert("L").resize((32, 32), PILImage.LANCZOS)
            pixels = list(gray.getdata())
            if not pixels:
                return False
            mean = sum(pixels) / len(pixels)
            var = sum((p - mean) ** 2 for p in pixels) / len(pixels)

            if strict:
                # Strict mode: for pages with text layer → only real embedded figures
                if var < 180:
                    return False
                rgb_small = im.convert("RGB").resize((16, 16))
                unique_colors = len(set(rgb_small.getdata()))
                if unique_colors < 10:
                    return False
                return True
            else:
                # Lenient mode: for image-based pages (scanned / pure image PDFs)
                # Include full-page content even if it's mostly text or has moderate flat areas
                if w > 350 and h > 450:
                    # Large image (likely the main page content)
                    if var > 25:  # allow sparse text on white
                        return True
                # Fallback to normal checks but lower thresholds
                if var < 80:
                    return False
                rgb_small = im.convert("RGB").resize((16, 16))
                unique_colors = len(set(rgb_small.getdata()))
                if unique_colors < 6:
                    return False
                return True
    except Exception:
        return len(data) > 8000


@dataclass
class ImageInspectResult:
    has_images: bool
    image_count: int
    file_type: str
    pages_with_images: list[int] = field(default_factory=list)
    text_extractable: bool = True


def inspect_result_to_dict(result: ImageInspectResult) -> dict:
    image_only = result.has_images and not result.text_extractable
    return {
        "has_images": result.has_images,
        "image_count": result.image_count,
        "file_type": result.file_type,
        "pages_with_images": result.pages_with_images,
        "text_extractable": result.text_extractable,
        "image_only": image_only,
    }


def inspect_document_bytes(content: bytes, extension: str) -> ImageInspectResult:
    ext = extension.lower()
    if ext in IMAGE_FILE_EXTENSIONS:
        return _inspect_image_file(content, ext)
    if ext not in {".pdf", ".docx"}:
        return ImageInspectResult(
            has_images=False,
            image_count=0,
            file_type=ext.lstrip(".") or "file",
        )
    try:
        if ext == ".pdf":
            return _inspect_pdf(content)
        return _inspect_docx(content)
    except Exception as exc:
        raise LoaderError("inspection_failed") from exc


def inspect_document_path(path: Path, extension: str) -> ImageInspectResult:
    return inspect_document_bytes(path.read_bytes(), extension)


def _inspect_pdf(content: bytes) -> ImageInspectResult:
    reader = PdfReader(io.BytesIO(content))
    pages_with_images: list[int] = []
    image_count = 0
    text_extractable = False

    for page_number, page in enumerate(reader.pages, start=1):
        page_text = (page.extract_text() or "").strip()
        if page_text:
            text_extractable = True
        page_images = 0
        is_text_page = bool(page_text)

        # pypdf loop + our heuristic is the sole inspection logic for has_images / count / pages.
        # (pdfimages is used only for high-quality *extraction* in the Vision-OCR path in vision_ocr.py)
        for image in page.images:
            if len(image.data) < MIN_IMAGE_BYTES:
                continue
            # On pages with extractable text layer: be strict (filter backgrounds)
            # On pages without text layer (scanned/image PDFs): be lenient so content images are offered for OCR
            if not _is_meaningful_image(image.data, strict=is_text_page):
                continue
            page_images += 1
        if page_images:
            pages_with_images.append(page_number)
            image_count += page_images

    return ImageInspectResult(
        has_images=image_count > 0,
        image_count=image_count,
        file_type="pdf",
        pages_with_images=pages_with_images,
        text_extractable=text_extractable,
    )


def _inspect_docx(content: bytes) -> ImageInspectResult:
    document = DocxDocument(io.BytesIO(content))
    image_count = 0
    text_extractable = any(paragraph.text.strip() for paragraph in document.paragraphs)
    for rel in document.part.rels.values():
        if "image" not in rel.target_ref:
            continue
        blob = rel.target_part.blob
        if len(blob) < MIN_IMAGE_BYTES:
            continue
        if not _is_meaningful_image(blob):  # filter low-info embedded (e.g. mini deco); realistic content passes
            continue
        image_count += 1
    return ImageInspectResult(
        has_images=image_count > 0,
        image_count=image_count,
        file_type="docx",
        text_extractable=text_extractable,
    )


def _inspect_image_file(content: bytes, extension: str) -> ImageInspectResult:
    """Standalone image files (user uploads) are always treated as images if PIL can open+verify them.
    No MIN size filter here — a small but valid PNG/JPG uploaded explicitly is meaningful content.
    (Embedded images in PDF/DOCX still use MIN + _is_meaningful_image to drop backgrounds/deco.)
    """
    file_type = extension.lstrip(".") or "image"
    try:
        with PILImage.open(io.BytesIO(content)) as im:
            im.verify()
        return ImageInspectResult(
            has_images=True,
            image_count=1,
            file_type=file_type,
            text_extractable=False,
        )
    except Exception:
        return ImageInspectResult(
            has_images=False,
            image_count=0,
            file_type=file_type,
            text_extractable=False,
        )
