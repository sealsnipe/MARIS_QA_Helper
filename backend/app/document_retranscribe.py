"""Nachverarbeitung offener Bilder eines bestehenden KB-Eintrags.

Grundlage sind die beim Upload archivierten Bild-Assets (data/uploads/<kunde>/
<doc>/images/) und die [BILD … status="nicht_verarbeitet"]-Platzhalter im
source_text: Die neue Transkription wird exakt an der Platzhalter-Stelle
eingesetzt, extraction_meta aktualisiert und der Eintrag neu indexiert.
"""

from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session

from app.batch_upload import report_batch_progress
from app.document_assets import (
    IMAGE_ID_PATTERN,
    format_image_block,
    images_from_meta,
    parse_extraction_meta,
    resolve_document_image_path,
)
from app.ingestion import get_document_text, reindex_document
from app.loaders.vision_ocr import merge_ocr_blocks, transcribe_images_pooled
from app.upload import UploadError


def retranscribe_document_images(
    db: Session,
    customer_id: str,
    document_id: str,
    image_ids: list[str],
    *,
    progress_token: str | None = None,
) -> dict | None:
    """Returns None when the document does not exist (route answers 404)."""
    try:
        return _retranscribe_inner(db, customer_id, document_id, image_ids, progress_token=progress_token)
    except Exception:
        report_batch_progress(progress_token, 100, "Abgebrochen.")
        raise


def _retranscribe_inner(
    db: Session,
    customer_id: str,
    document_id: str,
    image_ids: list[str],
    *,
    progress_token: str | None,
) -> dict | None:
    report = lambda percent, label: report_batch_progress(progress_token, percent, label)  # noqa: E731

    loaded = get_document_text(db, customer_id, document_id)
    if loaded is None:
        return None
    document, text = loaded

    requested = {item for item in image_ids if isinstance(item, str) and IMAGE_ID_PATTERN.match(item)}
    if not requested:
        raise UploadError("no_images_selected")

    meta = parse_extraction_meta(document.extraction_meta) or {}
    items = images_from_meta(meta)

    targets: list[tuple[dict, bytes, str]] = []
    missing: list[str] = []
    for item in items:
        image_id = item.get("id")
        if image_id not in requested or item.get("transcribed"):
            continue
        path = resolve_document_image_path(document, image_id)
        if path is None or not path.is_file():
            missing.append(image_id)
            continue
        targets.append((item, path.read_bytes(), item.get("mime_type") or "image/png"))

    if not targets:
        raise UploadError("image_assets_missing" if missing else "no_images_selected")

    total = len(targets)
    report(2, f"{total} Bild(er) in der Warteschlange…")

    def on_done(done: int, count: int) -> None:
        report(2 + 83 * done / max(count, 1), f"Vision-OCR {done}/{count} Bild(er) fertig…")

    results = transcribe_images_pooled([(data, mime) for _item, data, mime in targets], on_done=on_done)

    report(88, "Transkriptionen werden in den Eintrag eingefügt…")
    processed: list[str] = []
    failed: list[str] = []
    new_text = text
    for (item, _data, _mime), transcript in zip(targets, results):
        image_id = item["id"]
        if not transcript:
            failed.append(image_id)
            continue
        block = format_image_block(image_id=image_id, page=item.get("page"), transcription=transcript)
        placeholder = re.compile(rf'\[BILD id="{re.escape(image_id)}"[^\]]*status="nicht_verarbeitet"\]')
        new_text, replaced = placeholder.subn(block, new_text, count=1)
        if replaced == 0:
            # Alt-Eintrag ohne Platzhalter: Block ans Ende anhängen statt verlieren.
            new_text = merge_ocr_blocks(new_text, [block])
        item["transcribed"] = True
        processed.append(image_id)

    if not processed:
        raise UploadError("vision_failed")

    meta["images"] = items
    meta["images_processed"] = sum(1 for item in items if item.get("transcribed"))
    meta["vision_used"] = True
    image_count = meta.get("image_count") or len(items)
    meta["coverage"] = "full" if meta["images_processed"] >= image_count else "partial"

    document.source_text = new_text
    document.extraction_meta = json.dumps(meta)
    db.add(document)
    db.flush()

    report(92, "Eintrag wird neu indexiert…")
    result = reindex_document(db, customer_id, document_id)
    updated = result.document
    report(100, f"Fertig — {len(processed)} Bild(er) nachverarbeitet.")

    return {
        "processed": processed,
        "failed": failed,
        "missing": missing,
        "document": {
            "id": updated.id,
            "title": updated.title,
            "chunk_count": updated.chunk_count,
            "extraction_meta": parse_extraction_meta(updated.extraction_meta),
        },
    }
