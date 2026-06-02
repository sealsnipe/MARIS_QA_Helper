from __future__ import annotations

import re
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.chunking import normalize_text
from app.config import get_settings
from app.ingestion import IngestionError, ingest_text
from app.loaders import LoaderError, load_document, source_type_for_extension
from app.models import Document, utc_now_iso


class UploadError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


def sanitize_filename(name: str) -> str:
    base = Path(name).name
    cleaned = re.sub(r"[^\w.\- ]", "_", base).strip()
    return (cleaned or "upload")[:200]


def _upload_root() -> Path:
    return Path("./data/uploads")


def _combine_text(prefix_text: str, file_text: str) -> str:
    parts = [part.strip() for part in (prefix_text, file_text) if part.strip()]
    return "\n\n".join(parts)


def _resolve_title(title: str | None, filename: str | None) -> str:
    cleaned = (title or "").strip()
    if cleaned:
        return cleaned[:200]
    if filename:
        stem = Path(sanitize_filename(filename)).stem.strip()
        if stem:
            return stem[:200]
    return "Wissenseintrag"


def ingest_combined(
    db: Session,
    customer_id: str,
    *,
    title: str | None = None,
    prefix_text: str | None = None,
    filename: str | None = None,
    content: bytes | None = None,
    mime_type: str | None = None,
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

    if has_file:
        assert content is not None
        assert filename is not None
        safe_name = sanitize_filename(filename)
        extension = Path(safe_name).suffix.lower()

        if extension not in settings.allowed_extensions:
            raise UploadError("unsupported_file_type")

        if len(content) > settings.max_upload_bytes:
            raise UploadError("file_too_large")

        storage_dir = _upload_root() / customer_id / document_id
        storage_dir.mkdir(parents=True, exist_ok=True)
        stored_path = storage_dir / safe_name
        stored_path.write_bytes(content)
        file_source_type = source_type_for_extension(extension)

        try:
            file_text = load_document(stored_path, extension)
        except LoaderError as exc:
            doc_title = _resolve_title(title, safe_name)
            failed = Document(
                id=document_id,
                customer_id=customer_id,
                title=doc_title,
                source_type="file",
                original_filename=safe_name,
                mime_type=mime_type,
                storage_path=str(stored_path),
                chunk_count=0,
                status="failed",
                error_message=exc.args[0] if exc.args else "extraction_failed",
                created_at=utc_now_iso(),
                updated_at=utc_now_iso(),
            )
            db.add(failed)
            db.commit()
            db.refresh(failed)
            raise UploadError("extraction_failed") from exc

    combined = _combine_text(prefix, file_text)
    if len(normalize_text(combined)) < 20:
        raise UploadError("empty_text")

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
        )
    except IngestionError as exc:
        if exc.code == "empty_text":
            raise UploadError("empty_text") from exc
        raise

    return result.document
