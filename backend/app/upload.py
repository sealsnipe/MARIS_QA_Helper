from __future__ import annotations

import json
import re
import tempfile
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.chunking import normalize_text
from app.config import get_settings
from app.document_fingerprints import inspect_similarity_payload
from app.duplicates import duplicate_document_payload, find_duplicate_document
from app.ingestion import IngestionError, ingest_text
from app.loaders import LoaderError, load_document, source_type_for_extension
from app.document_assets import IMAGE_ID_PATTERN, SavedDocumentImage, build_image_preview_data_url, format_image_placeholder
from app.loaders.image_inspect import IMAGE_FILE_EXTENSIONS, ImageInspectResult, inspect_document_bytes, inspect_document_path, inspect_result_to_dict
from app.loaders.vision_ocr import (
    VisionOcrResult,
    append_pdf_image_blocks,
    compose_docx_with_vision,
    extract_embedded_images_from_bytes,
    merge_ocr_blocks,
    run_vision_ocr,
    save_embedded_images,
)
from app.models import Document


class UploadError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


def sanitize_filename(name: str) -> str:
    base = Path(name).name
    cleaned = re.sub(r"[^\w.\- ]", "_", base).strip()
    return (cleaned or "upload")[:200]


def parse_form_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return value.strip().lower() in {"true", "1", "yes", "on"}


def build_extraction_meta(
    *,
    image_count: int,
    images_processed: int,
    vision_used: bool,
    saved_images: list[SavedDocumentImage] | None = None,
) -> str:
    if image_count == 0 or images_processed >= image_count:
        coverage = "full"
    else:
        coverage = "partial"
    images = [
        {
            "id": item.id,
            "filename": item.filename,
            "page": item.page,
            "mime_type": item.mime_type,
            "transcribed": item.transcribed,
        }
        for item in (saved_images or [])
    ]
    return json.dumps(
        {
            "image_count": image_count,
            "images_processed": images_processed,
            "vision_used": vision_used,
            "coverage": coverage,
            "images": images,
        }
    )


def _upload_root() -> Path:
    return Path("./data/uploads")


def _discard_stored_upload(stored_path: Path | None) -> None:
    if stored_path is None or not stored_path.exists():
        return
    try:
        stored_path.unlink(missing_ok=True)
        parent = stored_path.parent
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
    except OSError:
        pass


def _combine_text(prefix_text: str, file_text: str) -> str:
    parts = [part.strip() for part in (prefix_text, file_text) if part.strip()]
    return "\n\n".join(parts)


def resolve_upload_source_text(
    *,
    prefix_text: str | None = None,
    filename: str | None = None,
    content: bytes | None = None,
) -> str:
    prefix = (prefix_text or "").strip()
    if content is None or not filename:
        return prefix

    safe_name, extension = _validate_upload_file(content, filename)
    if extension in {".txt", ".md", ".pdf", ".docx"}:
        try:
            file_text = _extract_upload_text(content, extension)
        except LoaderError:
            return prefix
        return _combine_text(prefix, file_text)
    return prefix


def inspect_text_content(
    db: Session,
    customer_id: str,
    text: str,
) -> dict:
    duplicate, similar, digest = _duplicate_payload_for_text(db, customer_id, text)
    return {
        "duplicate": duplicate,
        "similar": similar,
        "content_sha256": digest,
    }


def _resolve_title(title: str | None, filename: str | None) -> str:
    cleaned = (title or "").strip()
    if cleaned:
        return cleaned[:200]
    if filename:
        stem = Path(sanitize_filename(filename)).stem.strip()
        if stem:
            return stem[:200]
    return "Wissenseintrag"


def _validate_upload_file(content: bytes, filename: str) -> tuple[str, str]:
    settings = get_settings()
    safe_name = sanitize_filename(filename)
    extension = Path(safe_name).suffix.lower()
    if extension not in settings.allowed_extensions:
        raise UploadError("unsupported_file_type")
    if len(content) > settings.max_upload_bytes:
        raise UploadError("file_too_large")
    return safe_name, extension


def parse_transcribe_image_ids(value: str | None) -> set[str]:
    if value is None or not value.strip():
        return set()
    raw = value.strip()
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return set()
        if not isinstance(parsed, list):
            return set()
        ids = parsed
    else:
        ids = [part.strip() for part in raw.split(",") if part.strip()]
    return {item for item in ids if isinstance(item, str) and IMAGE_ID_PATTERN.match(item)}


def _inspect_images_payload(content: bytes, extension: str) -> list[dict]:
    images: list[dict] = []
    for image in extract_embedded_images_from_bytes(content, extension):
        image_id = image.image_id or f"img_{image.index:03d}"
        label = f"Seite {image.page}" if image.page is not None else image_id
        images.append(
            {
                "id": image_id,
                "page": image.page,
                "label": label,
                "preview_data_url": build_image_preview_data_url(image.data, image.mime_type),
            }
        )
    return images


def _extract_upload_text(content: bytes, extension: str) -> str:
    """Best-effort text extraction for duplicate checks (no Vision-OCR)."""
    ext = extension.lower()
    if ext in {".txt", ".md"}:
        for encoding in ("utf-8", "latin-1"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="replace")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=True) as tmp:
        tmp.write(content)
        tmp.flush()
        return load_document(Path(tmp.name), ext)


def _duplicate_payload_for_text(
    db: Session,
    customer_id: str,
    text: str,
) -> tuple[dict | None, list[dict], str | None]:
    return inspect_similarity_payload(db, customer_id, text)


def inspect_upload(
    db: Session,
    customer_id: str,
    content: bytes,
    filename: str,
    *,
    prefix_text: str | None = None,
) -> dict:
    safe_name, extension = _validate_upload_file(content, filename)
    prefix = (prefix_text or "").strip()

    if extension not in {".pdf", ".docx", *IMAGE_FILE_EXTENSIONS}:
        payload = {
            "has_images": False,
            "image_count": 0,
            "file_type": extension.lstrip(".") or "file",
            "pages_with_images": [],
            "text_extractable": True,
            "image_only": False,
            "filename": safe_name,
            "images": [],
        }
    else:
        try:
            result = inspect_document_bytes(content, extension)
        except LoaderError as exc:
            raise UploadError("inspection_failed") from exc

        payload = inspect_result_to_dict(result)
        payload["filename"] = safe_name
        payload["images"] = _inspect_images_payload(content, extension)

    combined_for_hash = prefix
    if extension in {".txt", ".md", ".pdf", ".docx"}:
        try:
            file_text = _extract_upload_text(content, extension)
            combined_for_hash = _combine_text(prefix, file_text)
        except LoaderError:
            combined_for_hash = prefix

    duplicate, similar, digest = _duplicate_payload_for_text(db, customer_id, combined_for_hash)
    payload["duplicate"] = duplicate
    payload["similar"] = similar
    payload["content_sha256"] = digest
    return payload


def ingest_combined(
    db: Session,
    customer_id: str,
    *,
    title: str | None = None,
    prefix_text: str | None = None,
    filename: str | None = None,
    content: bytes | None = None,
    mime_type: str | None = None,
    process_images: bool = False,
    transcribe_image_ids_raw: str | None = None,
    allow_duplicate: bool = False,
) -> Document:
    settings = get_settings()
    prefix = (prefix_text or "").strip()
    has_file = content is not None and filename

    if not prefix and not has_file:
        raise UploadError("empty_text")

    document_id = str(uuid.uuid4())
    safe_name: str | None = None
    stored_path: Path | None = None
    file_text = ""
    file_source_type = "manual"
    image_count = 0
    images_processed = 0
    vision_used = False
    extraction_meta: str | None = None

    if has_file:
        assert content is not None
        assert filename is not None
        safe_name, extension = _validate_upload_file(content, filename)
        file_source_type = source_type_for_extension(extension)

        storage_dir = _upload_root() / customer_id / document_id
        storage_dir.mkdir(parents=True, exist_ok=True)
        stored_path = storage_dir / safe_name
        stored_path.write_bytes(content)

        try:
            inspection = inspect_document_path(stored_path, extension)
        except LoaderError as exc:
            _discard_stored_upload(stored_path)
            raise UploadError("inspection_failed") from exc

        image_count = inspection.image_count
        saved_images: list[SavedDocumentImage] = []
        assets_dir = storage_dir / "images"

        file_text = ""
        try:
            file_text = load_document(stored_path, extension)
        except LoaderError as exc:
            if exc.args[0] != "extraction_failed" or (not inspection.has_images and not prefix):
                _discard_stored_upload(stored_path)
                raise UploadError("extraction_failed") from exc
            if inspection.has_images and not process_images and not prefix:
                _discard_stored_upload(stored_path)
                raise UploadError("images_only_requires_vision") from exc

        if inspection.has_images:
            saved_images = save_embedded_images(stored_path, extension, assets_dir)

        selected_ids: set[str] | None = None
        if transcribe_image_ids_raw is not None and transcribe_image_ids_raw.strip():
            selected_ids = parse_transcribe_image_ids(transcribe_image_ids_raw)

        wants_transcription = process_images and inspection.has_images and settings.vision_enabled
        if wants_transcription:
            ocr_result = run_vision_ocr(
                stored_path,
                extension,
                assets_dir=assets_dir,
                transcribe_ids=selected_ids,
                saved_images=saved_images,
            )
            saved_images = ocr_result.saved_images
            if extension == ".docx":
                file_text = compose_docx_with_vision(stored_path, ocr_result)
            elif extension == ".pdf":
                file_text = append_pdf_image_blocks(file_text, stored_path, ocr_result)
            elif extension in IMAGE_FILE_EXTENSIONS:
                file_text = merge_ocr_blocks(file_text, ocr_result.blocks)
            images_processed = ocr_result.images_processed
            vision_used = images_processed > 0
            if images_processed == 0:
                _discard_stored_upload(stored_path)
                raise UploadError("vision_failed")
        elif inspection.has_images:
            if extension == ".docx":
                from app.loaders.docx_content import compose_docx_text
                from docx import Document as DocxDocument

                document = DocxDocument(str(stored_path))
                interleaved = compose_docx_text(
                    document,
                    ocr_text_by_id={},
                    include_unprocessed_placeholders=True,
                ).strip()
                if interleaved:
                    file_text = interleaved
            elif extension == ".pdf" and saved_images:
                file_text = append_pdf_image_blocks(
                    file_text,
                    stored_path,
                    VisionOcrResult(blocks=[], images_processed=0, images_failed=0, saved_images=saved_images),
                )
            elif extension in IMAGE_FILE_EXTENSIONS and saved_images:
                file_text = merge_ocr_blocks(
                    file_text,
                    [format_image_placeholder(image_id=saved_images[0].id, page=None)],
                )

        extraction_meta = build_extraction_meta(
            image_count=image_count,
            images_processed=images_processed,
            vision_used=vision_used,
            saved_images=saved_images,
        )

    combined = _combine_text(prefix, file_text)
    if len(normalize_text(combined)) < 20:
        _discard_stored_upload(stored_path)
        raise UploadError("empty_text")

    if not allow_duplicate:
        duplicate = find_duplicate_document(db, customer_id, combined)
        if duplicate is not None:
            _discard_stored_upload(stored_path)
            raise UploadError(
                "duplicate_document",
                detail=json.dumps(duplicate_document_payload(duplicate)),
            )

    doc_title = _resolve_title(title, safe_name)
    source_type = file_source_type if file_text else "manual"

    try:
        result = ingest_text(
            db,
            customer_id=customer_id,
            title=doc_title,
            text=combined,
            source_type=source_type,
            document_id=document_id,
            original_filename=safe_name,
            mime_type=mime_type,
            storage_path=str(stored_path) if stored_path else None,
            extraction_meta=extraction_meta,
        )
    except IngestionError as exc:
        if exc.code == "empty_text":
            raise UploadError("empty_text") from exc
        raise

    return result.document
