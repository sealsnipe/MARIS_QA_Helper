"""Batch-Upload: mehrere Dateien (und ZIP-Archive) in einem Vorgang einpflegen.

Ablauf:
1. expand_batch_files: ZIPs öffnen, nur erlaubte Dateiformate übernehmen.
2. inspect_batch: pro Dokument Bild-Infos für die Auswahl im Frontend.
3. ingest_batch: jede Datei einzeln nacheinander verarbeiten (Extraktion + Vision),
   dann per LLM in KB-Einträge gruppieren (höchstens so viele Einträge wie
   Input-Dokumente) und sequenziell anlegen.
"""

from __future__ import annotations

import io
import json
import mimetypes
import re
import shutil
import tempfile
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.chunking import normalize_text
from app.config import get_settings
from app.document_assets import IMAGE_ID_PATTERN, SavedDocumentImage
from app.duplicates import duplicate_document_payload, find_duplicate_document
from app.ingestion import IngestionError, ingest_text
from app.loaders import LoaderError, load_document, source_type_for_extension
from app.loaders.image_inspect import IMAGE_FILE_EXTENSIONS, inspect_document_bytes, inspect_result_to_dict
from app.loaders.vision_ocr import (
    VisionOcrResult,
    append_pdf_image_blocks,
    compose_docx_with_vision,
    merge_ocr_blocks,
    run_vision_ocr,
    save_embedded_images,
)
from app.models import Document
import app.upload as upload_lib
from app.upload import (
    UploadError,
    _apply_title_rule,
    _combine_text,
    _inspect_images_payload,
    _upload_root,
    build_extraction_meta,
    sanitize_filename,
)

ZIP_EXTENSION = ".zip"
MAX_BATCH_FILES = 20

_IMAGE_ID_TOKEN = re.compile(r"\bimg_(\d{3})\b")


@dataclass
class BatchFile:
    key: str
    filename: str
    content: bytes
    extension: str
    source_zip: str | None = None


@dataclass
class ExtractedDoc:
    file: BatchFile
    text: str = ""
    image_count: int = 0
    images_processed: int = 0
    saved_images: list[SavedDocumentImage] = field(default_factory=list)
    assets_dir: Path | None = None
    error: str | None = None

    @property
    def has_content(self) -> bool:
        """True if there is real content beyond unprocessed image placeholders."""
        without_placeholders = re.sub(r'\[BILD[^\]]*status="nicht_verarbeitet"\]', "", self.text)
        return len(normalize_text(without_placeholders)) >= 20


def _is_hidden_zip_member(name: str) -> bool:
    parts = Path(name).parts
    return any(part.startswith(".") or part == "__MACOSX" for part in parts)


def expand_batch_files(uploads: list[tuple[str, bytes]]) -> tuple[list[BatchFile], list[dict]]:
    """Flatten uploads into processable files; ZIPs are expanded in member order.

    Unsupported or oversized files (direct or inside a ZIP) are skipped with a
    reason instead of failing the whole batch.
    """
    settings = get_settings()
    allowed = settings.allowed_extensions
    files: list[BatchFile] = []
    skipped: list[dict] = []

    def add_file(key: str, filename: str, content: bytes, source_zip: str | None) -> None:
        safe_name = sanitize_filename(filename)
        extension = Path(safe_name).suffix.lower()
        display = f"{source_zip}/{safe_name}" if source_zip else safe_name
        if extension not in allowed:
            skipped.append({"filename": display, "reason": "unsupported_file_type"})
            return
        if len(content) > settings.max_upload_bytes:
            skipped.append({"filename": display, "reason": "file_too_large"})
            return
        if len(files) >= MAX_BATCH_FILES:
            raise UploadError("too_many_files")
        files.append(
            BatchFile(key=key, filename=safe_name, content=content, extension=extension, source_zip=source_zip)
        )

    for index, (filename, content) in enumerate(uploads):
        extension = Path(sanitize_filename(filename)).suffix.lower()
        if extension == ZIP_EXTENSION:
            zip_name = sanitize_filename(filename)
            try:
                archive = zipfile.ZipFile(io.BytesIO(content))
            except zipfile.BadZipFile as exc:
                raise UploadError("invalid_zip") from exc
            with archive:
                for info in archive.infolist():
                    if info.is_dir() or _is_hidden_zip_member(info.filename):
                        continue
                    member_ext = Path(info.filename).suffix.lower()
                    if member_ext == ZIP_EXTENSION:
                        skipped.append({"filename": f"{zip_name}/{info.filename}", "reason": "nested_zip"})
                        continue
                    if info.file_size > settings.max_upload_bytes:
                        skipped.append({"filename": f"{zip_name}/{info.filename}", "reason": "file_too_large"})
                        continue
                    add_file(
                        key=f"f{index}:{info.filename}",
                        filename=Path(info.filename).name,
                        content=archive.read(info),
                        source_zip=zip_name,
                    )
        else:
            add_file(key=f"f{index}", filename=filename, content=content, source_zip=None)

    if not files:
        raise UploadError("no_supported_files")
    return files, skipped


def inspect_batch(db: Session, customer_id: str, uploads: list[tuple[str, bytes]]) -> dict:
    files, skipped = expand_batch_files(uploads)
    documents: list[dict] = []
    for batch_file in files:
        entry: dict = {
            "key": batch_file.key,
            "filename": batch_file.filename,
            "source_zip": batch_file.source_zip,
            "file_type": batch_file.extension.lstrip("."),
            "has_images": False,
            "image_count": 0,
            "image_only": False,
            "images": [],
        }
        if batch_file.extension in {".pdf", ".docx", *IMAGE_FILE_EXTENSIONS}:
            try:
                result = inspect_document_bytes(batch_file.content, batch_file.extension)
            except LoaderError:
                entry["error"] = "inspection_failed"
            else:
                payload = inspect_result_to_dict(result)
                entry["has_images"] = payload.get("has_images", False)
                entry["image_count"] = payload.get("image_count", 0)
                entry["image_only"] = payload.get("image_only", False)
                if entry["has_images"]:
                    entry["images"] = _inspect_images_payload(batch_file.content, batch_file.extension)
        documents.append(entry)
    return {"documents": documents, "skipped": skipped, "file_count": len(files)}


GROUPING_PROMPT = """\
Du planst Einträge für eine Support-Wissensdatenbank.
Gegeben sind mehrere hochgeladene Dokumente (Index, Dateiname, Auszug). Bewerte die Inhalte und entscheide, welche Dokumente inhaltlich so eng zusammengehören, dass sie EIN gemeinsamer Eintrag sein sollten. Unabhängige Themen bleiben eigene Einträge.
Regeln:
- Höchstens so viele Einträge wie Dokumente, mindestens 1.
- Jeder Dokument-Index wird GENAU EINEM Eintrag zugeordnet.
- Pro Eintrag ein Titel aus 1-5 kurzen Schlagworten (je 1-3 Wörter), getrennt durch " + ", die wichtigsten zuerst. Nur so viele wie nötig.
Antworte AUSSCHLIESSLICH mit gültigem JSON, kein Markdown:
{"entries": [{"files": [0, 2], "title": "schlagwort1 + schlagwort2"}, {"files": [1], "title": "…"}]}"""


def _strip_json_fence(raw: str) -> str:
    stripped = raw.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else stripped


def _validate_plan(payload: object, count: int) -> list[dict] | None:
    if not isinstance(payload, dict):
        return None
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries or len(entries) > count:
        return None
    seen: set[int] = set()
    plan: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            return None
        indices = entry.get("files")
        if not isinstance(indices, list) or not indices:
            return None
        clean: list[int] = []
        for idx in indices:
            if not isinstance(idx, int) or isinstance(idx, bool) or idx < 0 or idx >= count or idx in seen:
                return None
            seen.add(idx)
            clean.append(idx)
        title = entry.get("title")
        title = title.strip() if isinstance(title, str) and title.strip() else None
        plan.append({"indices": sorted(clean), "title": title})
    if len(seen) != count:
        return None
    return plan


def plan_kb_entries(db: Session, docs: list[ExtractedDoc]) -> list[dict]:
    """LLM-Gruppierung der Dokumente in KB-Einträge (≤ Anzahl Dokumente).

    Fallback bei jedem Fehler: ein Eintrag pro Dokument.
    """
    singletons = [{"indices": [i], "title": None} for i in range(len(docs))]
    if len(docs) <= 1:
        return singletons

    from app.llm import get_llm

    lines = []
    for i, doc in enumerate(docs):
        excerpt = normalize_text(doc.text)[:600]
        lines.append(f"[{i}] {doc.file.filename}\n{excerpt}")
    try:
        response = get_llm(db=db).chat(
            [
                {"role": "system", "content": GROUPING_PROMPT},
                {"role": "user", "content": "\n\n---\n\n".join(lines)},
            ]
        )
        raw = _strip_json_fence((response.content or "").strip())
        payload = json.loads(raw)
    except Exception:
        return singletons
    plan = _validate_plan(payload, len(docs))
    return plan if plan is not None else singletons


def _parse_transcribe_map(raw: str | None) -> dict[str, set[str]]:
    if not raw or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    result: dict[str, set[str]] = {}
    for key, ids in parsed.items():
        if not isinstance(ids, list):
            continue
        valid = {item for item in ids if isinstance(item, str) and IMAGE_ID_PATTERN.match(item)}
        if valid:
            result[str(key)] = valid
    return result


def _process_file(
    batch_file: BatchFile,
    work_dir: Path,
    *,
    process_images: bool,
    transcribe_ids: set[str],
) -> ExtractedDoc:
    settings = get_settings()
    doc = ExtractedDoc(file=batch_file)
    work_dir.mkdir(parents=True, exist_ok=True)
    path = work_dir / batch_file.filename
    path.write_bytes(batch_file.content)
    assets_dir = work_dir / "images"
    extension = batch_file.extension

    has_images = False
    if extension in {".pdf", ".docx", *IMAGE_FILE_EXTENSIONS}:
        try:
            inspection = inspect_document_bytes(batch_file.content, extension)
            has_images = inspection.has_images
            doc.image_count = inspection.image_count
        except LoaderError:
            has_images = False

    file_text = ""
    try:
        file_text = load_document(path, extension)
    except LoaderError:
        file_text = ""

    saved_images: list[SavedDocumentImage] = []
    if has_images:
        try:
            saved_images = save_embedded_images(path, extension, assets_dir)
        except Exception:
            saved_images = []

    wants_transcription = process_images and has_images and bool(transcribe_ids) and settings.vision_enabled
    if wants_transcription:
        ocr_result = run_vision_ocr(
            path,
            extension,
            assets_dir=assets_dir,
            transcribe_ids=transcribe_ids,
            saved_images=saved_images,
        )
        saved_images = ocr_result.saved_images
        if extension == ".docx":
            file_text = compose_docx_with_vision(path, ocr_result)
        elif extension == ".pdf":
            file_text = append_pdf_image_blocks(file_text, path, ocr_result)
        elif extension in IMAGE_FILE_EXTENSIONS:
            file_text = merge_ocr_blocks(file_text, ocr_result.blocks)
        doc.images_processed = ocr_result.images_processed
    elif has_images:
        empty_result = VisionOcrResult(blocks=[], images_processed=0, images_failed=0, saved_images=saved_images)
        if extension == ".docx":
            file_text = compose_docx_with_vision(path, empty_result)
        elif extension == ".pdf":
            file_text = append_pdf_image_blocks(file_text, path, empty_result)
        elif extension in IMAGE_FILE_EXTENSIONS and saved_images:
            from app.document_assets import format_image_placeholder

            file_text = merge_ocr_blocks(
                file_text, [format_image_placeholder(image_id=saved_images[0].id, page=None)]
            )

    doc.text = file_text
    doc.saved_images = saved_images
    doc.assets_dir = assets_dir
    if not doc.has_content:
        doc.error = "no_text_content"
    return doc


def _merge_group(members: list[ExtractedDoc]) -> tuple[str, list[SavedDocumentImage], list[tuple[str, Path]], int, int]:
    """Combine member docs into one entry text with globally renumbered image ids.

    Returns (text, saved_images, asset_copies [(new_filename, source_path)], image_count, images_processed).
    """
    sections: list[str] = []
    merged_images: list[SavedDocumentImage] = []
    asset_copies: list[tuple[str, Path]] = []
    counter = 0
    image_count = 0
    images_processed = 0

    for member in members:
        mapping: dict[str, str] = {}
        for image in member.saved_images:
            counter += 1
            mapping[image.id] = f"img_{counter:03d}"

        text = member.text
        if mapping:
            text = _IMAGE_ID_TOKEN.sub(lambda m: mapping.get(m.group(0), m.group(0)), text)
        for image in member.saved_images:
            new_id = mapping[image.id]
            suffix = Path(image.filename).suffix
            new_filename = f"{new_id}{suffix}"
            if member.assets_dir is not None:
                source = member.assets_dir / image.filename
                if source.exists():
                    asset_copies.append((new_filename, source))
            merged_images.append(
                SavedDocumentImage(
                    id=new_id,
                    filename=new_filename,
                    page=image.page,
                    mime_type=image.mime_type,
                    transcribed=image.transcribed,
                )
            )

        if len(members) > 1:
            sections.append(f"## {member.file.filename}\n\n{text.strip()}")
        else:
            sections.append(text.strip())
        image_count += member.image_count
        images_processed += member.images_processed

    return "\n\n".join(sections), merged_images, asset_copies, image_count, images_processed


def _entry_title(
    db: Session,
    customer_id: str,
    *,
    group_title: str | None,
    user_title: str | None,
    single_entry: bool,
    text: str,
    members: list[ExtractedDoc],
) -> str:
    if single_entry and user_title and user_title.strip():
        return _apply_title_rule(customer_id, user_title.strip())
    if group_title:
        return _apply_title_rule(customer_id, group_title)
    # Modul-Attribut statt direktem Import: bleibt monkeypatch-bar (Tests stubben app.upload).
    generated = upload_lib.generate_title_keywords(db, text)
    if generated:
        return _apply_title_rule(customer_id, generated)
    stem = Path(members[0].file.filename).stem.strip() or "Wissenseintrag"
    return _apply_title_rule(customer_id, stem)


def ingest_batch(
    db: Session,
    customer_id: str,
    uploads: list[tuple[str, bytes]],
    *,
    title: str | None = None,
    prefix_text: str | None = None,
    process_images: bool = False,
    transcribe_map_raw: str | None = None,
    allow_duplicate: bool = False,
) -> dict:
    files, skipped = expand_batch_files(uploads)
    transcribe_map = _parse_transcribe_map(transcribe_map_raw)
    prefix = (prefix_text or "").strip()
    entries: list[dict] = []
    failed: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="batch-upload-") as tmp:
        tmp_root = Path(tmp)
        docs: list[ExtractedDoc] = []
        for index, batch_file in enumerate(files):
            doc = _process_file(
                batch_file,
                tmp_root / f"doc_{index}",
                process_images=process_images,
                transcribe_ids=transcribe_map.get(batch_file.key, set()),
            )
            docs.append(doc)

        usable = [doc for doc in docs if doc.error is None]
        failed = [
            {"filename": doc.file.filename, "source_zip": doc.file.source_zip, "error": doc.error}
            for doc in docs
            if doc.error is not None
        ]
        if not usable:
            raise UploadError("no_text_content")

        plan = plan_kb_entries(db, usable)

        for group_index, group in enumerate(plan):
            members = [usable[i] for i in group["indices"]]
            text, merged_images, asset_copies, image_count, images_processed = _merge_group(members)
            if group_index == 0 and prefix:
                text = _combine_text(prefix, text)
            filenames = [m.file.filename for m in members]

            if not allow_duplicate:
                duplicate = find_duplicate_document(db, customer_id, text)
                if duplicate is not None:
                    entries.append(
                        {
                            "status": "duplicate",
                            "filenames": filenames,
                            "duplicate": duplicate_document_payload(duplicate),
                        }
                    )
                    continue

            entry_title = _entry_title(
                db,
                customer_id,
                group_title=group["title"],
                user_title=title,
                single_entry=len(plan) == 1,
                text=text,
                members=members,
            )

            document_id = str(uuid.uuid4())
            storage_dir = _upload_root() / customer_id / document_id
            storage_dir.mkdir(parents=True, exist_ok=True)
            stored_path: Path | None = None
            for member in members:
                target = storage_dir / member.file.filename
                if target.exists():
                    target = storage_dir / f"{target.stem}_{uuid.uuid4().hex[:6]}{target.suffix}"
                target.write_bytes(member.file.content)
                if stored_path is None:
                    stored_path = target
            assets_dir = storage_dir / "images"
            for new_filename, source in asset_copies:
                assets_dir.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, assets_dir / new_filename)

            extraction_meta = build_extraction_meta(
                image_count=image_count,
                images_processed=images_processed,
                vision_used=images_processed > 0,
                saved_images=merged_images,
            )
            mime_type = mimetypes.guess_type(members[0].file.filename)[0]

            try:
                result = ingest_text(
                    db,
                    customer_id=customer_id,
                    title=entry_title,
                    text=text,
                    source_type=source_type_for_extension(members[0].file.extension),
                    document_id=document_id,
                    original_filename=members[0].file.filename,
                    mime_type=mime_type,
                    storage_path=str(stored_path) if stored_path else None,
                    extraction_meta=extraction_meta,
                )
            except IngestionError as exc:
                shutil.rmtree(storage_dir, ignore_errors=True)
                entries.append({"status": "failed", "filenames": filenames, "error": exc.code})
                continue

            document: Document = result.document
            entries.append(
                {
                    "status": "created",
                    "filenames": filenames,
                    "document": {
                        "id": document.id,
                        "title": document.title,
                        "chunk_count": document.chunk_count,
                    },
                }
            )

    return {"entries": entries, "skipped": skipped, "failed": failed, "file_count": len(files)}
