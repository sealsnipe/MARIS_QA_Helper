from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document as DocxDocument
from PIL import Image as PILImage
from pypdf import PdfReader

from app.loaders.errors import LoaderError

MIN_IMAGE_BYTES = 1024  # base size filter; stricter content checks below

IMAGE_FILE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})


def _is_meaningful_image(data: bytes) -> bool:
    """Heuristic to decide if an embedded PDF/DOCX image is real content worth Vision-OCR.

    Filters out:
    - Tiny icons/decorations
    - Page background "paper" textures or low-information gradients (common in designed PDFs)
    - Very uniform or low-detail images

    A page with only such "background images" should not be treated as having images for OCR purposes.
    Real screenshots, diagrams, photos, figures will pass.
    """
    if len(data) < MIN_IMAGE_BYTES:
        return False
    try:
        with PILImage.open(io.BytesIO(data)) as im:
            w, h = im.size
            if w < 160 or h < 160:
                return False

            # Low variance / low information test (grayscale small sample)
            gray = im.convert("L").resize((32, 32), PILImage.LANCZOS)
            pixels = list(gray.getdata())
            if not pixels:
                return False
            mean = sum(pixels) / len(pixels)
            var = sum((p - mean) ** 2 for p in pixels) / len(pixels)
            if var < 180:  # quite flat (solid bg, light gradient, watermark)
                return False

            # Color diversity on very small RGB sample
            rgb_small = im.convert("RGB").resize((16, 16))
            unique_colors = len(set(rgb_small.getdata()))
            if unique_colors < 10:
                return False

            return True
    except Exception:
        # If we can't parse the image bytes, fall back to generous size threshold
        # (real content images are usually larger anyway)
        return len(data) > 12000


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
        if (page.extract_text() or "").strip():
            text_extractable = True
        page_images = 0
        for image in page.images:
            if len(image.data) < MIN_IMAGE_BYTES:
                continue
            if not _is_meaningful_image(image.data):
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
        image_count += 1
    return ImageInspectResult(
        has_images=image_count > 0,
        image_count=image_count,
        file_type="docx",
        text_extractable=text_extractable,
    )


def _inspect_image_file(content: bytes, extension: str) -> ImageInspectResult:
    file_type = extension.lstrip(".") or "image"
    if len(content) < MIN_IMAGE_BYTES:
        return ImageInspectResult(
            has_images=False,
            image_count=0,
            file_type=file_type,
            text_extractable=False,
        )
    return ImageInspectResult(
        has_images=True,
        image_count=1,
        file_type=file_type,
        text_extractable=False,
    )
