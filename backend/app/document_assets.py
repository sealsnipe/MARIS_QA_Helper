from __future__ import annotations

import base64
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from app.models import Document

IMAGE_ID_PATTERN = re.compile(r"^img_\d{3}$")


@dataclass
class SavedDocumentImage:
    id: str
    filename: str
    page: int | None
    mime_type: str
    transcribed: bool = False


def mime_to_extension(mime_type: str) -> str:
    mapping = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }
    return mapping.get(mime_type, ".png")


def format_image_block(*, image_id: str, page: int | None, transcription: str) -> str:
    page_attr = f' seite="{page}"' if page is not None else ""
    return f'[BILD id="{image_id}"{page_attr}]\n{transcription.strip()}\n[/BILD]'


def format_image_placeholder(*, image_id: str, page: int | None) -> str:
    page_attr = f' seite="{page}"' if page is not None else ""
    return f'[BILD id="{image_id}"{page_attr} status="nicht_verarbeitet"]'


def build_image_preview_data_url(data: bytes, mime_type: str, *, max_size: int = 240) -> str:
    preview_bytes = data
    preview_mime = mime_type
    try:
        image = Image.open(io.BytesIO(data))
        image.thumbnail((max_size, max_size))
        buffer = io.BytesIO()
        if image.mode in {"RGBA", "P"}:
            image = image.convert("RGB")
            save_format = "JPEG"
            preview_mime = "image/jpeg"
        elif mime_type == "image/jpeg":
            save_format = "JPEG"
        else:
            save_format = "PNG"
            preview_mime = "image/png"
        image.save(buffer, format=save_format)
        preview_bytes = buffer.getvalue()
    except Exception:
        preview_bytes = data
        preview_mime = mime_type
    encoded = base64.b64encode(preview_bytes).decode("ascii")
    return f"data:{preview_mime};base64,{encoded}"


def save_document_image(assets_dir: Path, *, image_id: str, page: int | None, data: bytes, mime_type: str) -> SavedDocumentImage:
    assets_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{image_id}{mime_to_extension(mime_type)}"
    (assets_dir / filename).write_bytes(data)
    return SavedDocumentImage(id=image_id, filename=filename, page=page, mime_type=mime_type)


def parse_extraction_meta(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def images_from_meta(meta: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not meta:
        return []
    images = meta.get("images")
    return images if isinstance(images, list) else []


def document_images_dir(document: Document) -> Path | None:
    if not document.storage_path:
        return None
    return Path(document.storage_path).parent / "images"


def resolve_document_image_path(document: Document, image_id: str) -> Path | None:
    if not IMAGE_ID_PATTERN.match(image_id):
        return None
    images_dir = document_images_dir(document)
    if images_dir is None or not images_dir.is_dir():
        return None

    meta = parse_extraction_meta(document.extraction_meta)
    for item in images_from_meta(meta):
        if item.get("id") == image_id:
            filename = item.get("filename")
            if isinstance(filename, str):
                candidate = images_dir / filename
                if candidate.is_file():
                    return candidate

    matches = list(images_dir.glob(f"{image_id}.*"))
    if len(matches) == 1:
        return matches[0]
    return None


def image_payloads(document: Document, *, base_url: str) -> list[dict[str, Any]]:
    meta = parse_extraction_meta(document.extraction_meta)
    payloads: list[dict[str, Any]] = []
    for item in images_from_meta(meta):
        image_id = item.get("id")
        if not isinstance(image_id, str):
            continue
        payloads.append(
            {
                "id": image_id,
                "filename": item.get("filename"),
                "page": item.get("page"),
                "mime_type": item.get("mime_type"),
                "transcribed": bool(item.get("transcribed")),
                "url": f"{base_url.rstrip('/')}/images/{image_id}",
            }
        )
    return payloads
