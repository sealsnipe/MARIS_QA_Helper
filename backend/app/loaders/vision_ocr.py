from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.loaders.docx_content import compose_docx_text, extract_docx_images_ordered
from docx import Document as DocxDocument
from pypdf import PdfReader

from app.config import get_settings
from app.document_assets import (
    SavedDocumentImage,
    format_image_block,
    format_image_placeholder,
    save_document_image,
)
from app.llm import LLMError, transcribe_image
from app.loaders.image_inspect import (
    MIN_IMAGE_BYTES,
    IMAGE_FILE_EXTENSIONS,
    _is_meaningful_image,
    _has_pdfimages,
    _extract_images_pdfimages,
)

OCR_PROMPT = """\
Du transkribierst Bilder für eine Wissensdatenbank. Entscheide SELBST, welcher Fall zutrifft — der Nutzer wählt nicht.

Schritt 1 — Bildtyp erkennen (intern, nicht ausgeben):
- FALL A (Textbild): überwiegend Fließtext, Listen, Überschriften, Screenshots von Artikeln/Dokumenten — ohne erkennbare grafische Struktur mit Verknüpfungen zwischen Elementen.
- FALL B (Darstellung): Bilder mit visueller Struktur — Diagramme, Abläufe mit Pfeilen/Linien zwischen beschrifteten Elementen, Tabellen als Grafik, Fotos, Skizzen, Mockups.

Schritt 2 — Ausgabe (NUR das Ergebnis, keine Meta-Kommentare, keine Überschrift wie "Transkription" oder "UI-Beschreibung"):

FALL A — reiner Textinhalt:
- Gib den lesbaren Inhalt wörtlich wieder (Sprache des Bildes beibehalten).
- Struktur beibehalten: nummerierte Listen, Aufzählungen, Absätze, Überschriften.
- WEGLASSEN (nicht in die KB): Website-Chrome und Dekoration — z. B. Quellen-Badges ("Wikipedia +2"), Icon-Buttons, Share/Link-Chips, Navigationsleisten, Cookie-Hinweise, Werbung.
- WEGLASSEN: Beschreibungen von Formatierung (kein "blauer unterstrichener Link", keine Farben/Schriftarten/Layout).
- Links: nur den sichtbaren Linktext übernehmen; URL nur wenn vollständig lesbar, sonst weglassen.
- Keine Icon-Namen erfinden; nur Text, der auf dem Bild steht.
- Unleserlich: [unleserlich]; abgeschnitten: [… abgeschnitten …].

FALL B — Darstellung / Diagramm / Foto:
Nur Beschriftungen oder Stichworte aufzulisten reicht NICHT. Erfasse Text UND die visuelle Struktur: was mit wem verbunden ist, in welcher Richtung, und was die Verbindung bedeutet.

Pflichtinhalt in "text" (Sprache des Bildes beibehalten):
- Titel und Legende wörtlich, wenn sichtbar.
- Kurzer Kontext in einem Satz — ohne Floskeln wie „Das Bild zeigt …".
- Alle beschrifteten Elemente vollständig (Nummer/Name und Text); keine lose, ungeordnete Liste.
- Beziehungen und Ablauf — eigener Abschnitt, der explizit beschreibt:
  • welches Element mit welchem verbunden ist (Pfeile, Linien, Kanten, Pfeilrichtung)
  • parallele Zweige, Verzweigungen und Zusammenführungen
  • Bedeutung der Verknüpfung, soweit aus Legende, Beschriftung oder Kontext ersichtlich
  • unterschiedliche Linien- oder Pfeiltypen nur soweit Legende oder Beschriftung es vorgibt
- Visuelle tragende Elemente knapp benennen (z. B. Knoten, Pfeil, gestrichelte Linie, Gruppe) — ohne Farb-/Schrift-Kommentare.
- Tabellen: als Markdown-Tabelle; Fotos: sachliche Beschreibung plus sichtbarer Text.
- Nichts erfinden, nichts weglassen. Eine reine Textliste ohne Beschreibung der Verknüpfungen ist in Fall B unvollständig.

Allgemein: Keine Zusammenfassung in FALL A. Keine doppelte Wiederholung.

Antwortformat — AUSSCHLIESSLICH gültiges JSON, kein Markdown drumherum:
{"text": "…", "mermaid": null}

- "text": nur die Transkription (Fall A oder B), ohne Mermaid-Code.
- "mermaid": nur wenn die Darstellung als Knoten-Kanten-Diagramm sinnvoll abbildbar ist — dann valider Mermaid-Code. Sonst null. Kein Mermaid in "text" wiederholen."""


def _strip_json_fence(raw: str) -> str:
    stripped = raw.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else stripped


def parse_ocr_response(raw: str) -> tuple[str, str | None]:
    """Parse vision OCR output into plain text and optional mermaid diagram code."""
    cleaned = _strip_json_fence(raw.strip())
    if cleaned.startswith("{"):
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            return cleaned, None
        if not isinstance(payload, dict):
            return cleaned, None
        text = str(payload.get("text") or "").strip()
        mermaid_raw = payload.get("mermaid")
        mermaid = str(mermaid_raw).strip() if mermaid_raw else None
        if mermaid:
            mermaid = re.sub(r"^```(?:mermaid)?\s*", "", mermaid, flags=re.IGNORECASE)
            mermaid = re.sub(r"\s*```$", "", mermaid).strip() or None
        return text or cleaned, mermaid
    return cleaned, None


@dataclass
class EmbeddedImage:
    index: int
    page: int | None
    data: bytes
    mime_type: str
    image_id: str | None = None


@dataclass
class VisionOcrResult:
    blocks: list[str]
    images_processed: int
    images_failed: int
    saved_images: list[SavedDocumentImage] = field(default_factory=list)


def extract_embedded_images(path: Path, extension: str) -> list[EmbeddedImage]:
    return extract_embedded_images_from_bytes(path.read_bytes(), extension)


def extract_embedded_images_from_bytes(content: bytes, extension: str) -> list[EmbeddedImage]:
    ext = extension.lower()
    if ext in IMAGE_FILE_EXTENSIONS:
        return _extract_standalone_image(content, ext)
    if ext == ".pdf":
        return _extract_pdf_images(content)
    if ext == ".docx":
        return _extract_docx_images(content)
    return []


def save_embedded_images(path: Path, extension: str, assets_dir: Path) -> list[SavedDocumentImage]:
    saved_images: list[SavedDocumentImage] = []
    for image in extract_embedded_images(path, extension):
        image_id = _image_id(image)
        saved = save_document_image(
            assets_dir,
            image_id=image_id,
            page=image.page,
            data=image.data,
            mime_type=image.mime_type,
        )
        saved.transcribed = False
        saved_images.append(saved)
    return saved_images


def run_vision_ocr(
    path: Path,
    extension: str,
    assets_dir: Path | None = None,
    *,
    transcribe_ids: set[str] | None = None,
    saved_images: list[SavedDocumentImage] | None = None,
) -> VisionOcrResult:
    settings = get_settings()
    if not settings.vision_enabled:
        return VisionOcrResult(blocks=[], images_processed=0, images_failed=0, saved_images=saved_images or [])

    images = extract_embedded_images(path, extension)[: settings.vision_max_images]
    blocks: list[str] = []
    output_saved = list(saved_images or [])
    saved_by_id = {item.id: item for item in output_saved}
    processed = 0
    failed = 0

    for image in images:
        image_id = _image_id(image)
        if transcribe_ids is not None and image_id not in transcribe_ids:
            continue

        if assets_dir is not None and image_id not in saved_by_id:
            saved = save_document_image(
                assets_dir,
                image_id=image_id,
                page=image.page,
                data=image.data,
                mime_type=image.mime_type,
            )
            saved.transcribed = False
            saved_by_id[image_id] = saved
            output_saved.append(saved)

        try:
            raw = transcribe_image(image.data, image.mime_type, prompt=OCR_PROMPT).strip()
            text, _mermaid = parse_ocr_response(raw)
        except LLMError:
            failed += 1
            continue
        if not text:
            failed += 1
            continue

        blocks.append(format_image_block(image_id=image_id, page=image.page, transcription=text))
        if image_id in saved_by_id:
            saved_by_id[image_id].transcribed = True
        processed += 1

    return VisionOcrResult(
        blocks=blocks,
        images_processed=processed,
        images_failed=failed,
        saved_images=output_saved,
    )


def merge_ocr_blocks(base_text: str, blocks: list[str]) -> str:
    if not blocks:
        return base_text
    ocr_section = "\n\n".join(blocks)
    if base_text.strip():
        return f"{base_text.strip()}\n\n{ocr_section}"
    return ocr_section


def compose_docx_with_vision(path: Path, ocr_result: VisionOcrResult) -> str:
    ocr_by_id = _ocr_text_by_id_from_blocks(ocr_result.blocks)
    document = DocxDocument(str(path))
    return compose_docx_text(
        document,
        ocr_text_by_id=ocr_by_id,
        include_unprocessed_placeholders=True,
    )


def append_pdf_image_blocks(base_text: str, path: Path, ocr_result: VisionOcrResult) -> str:
    ocr_by_id = _ocr_text_by_id_from_blocks(ocr_result.blocks)
    blocks: list[str] = []
    for image in extract_embedded_images(path, ".pdf"):
        image_id = _image_id(image)
        if image_id in ocr_by_id:
            blocks.append(
                format_image_block(
                    image_id=image_id,
                    page=image.page,
                    transcription=ocr_by_id[image_id],
                )
            )
        else:
            blocks.append(format_image_placeholder(image_id=image_id, page=image.page))
    return merge_ocr_blocks(base_text, blocks)


def _ocr_text_by_id_from_blocks(blocks: list[str]) -> dict[str, str]:
    ocr_by_id: dict[str, str] = {}
    for block in blocks:
        match = re.search(r'id="(img_\d{3})"', block)
        if not match:
            continue
        body_start = block.find("]\n")
        body_end = block.rfind("\n[/BILD]")
        if body_start == -1 or body_end == -1:
            continue
        ocr_by_id[match.group(1)] = block[body_start + 2 : body_end].strip()
    return ocr_by_id


def _image_id(image: EmbeddedImage) -> str:
    return image.image_id or f"img_{image.index:03d}"


def _extract_standalone_image(content: bytes, extension: str) -> list[EmbeddedImage]:
    if len(content) < MIN_IMAGE_BYTES:
        return []
    return [
        EmbeddedImage(
            index=1,
            page=None,
            data=content,
            mime_type=_mime_from_extension(extension),
            image_id="img_001",
        )
    ]


def _mime_from_extension(extension: str) -> str:
    mapping = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return mapping.get(extension.lower(), "image/png")


def _extract_pdf_images(content: bytes) -> list[EmbeddedImage]:
    """
    Extract embedded images. Prefers pdfimages (from poppler-utils) when available
    for original embedded quality (no resampling, native formats/resolution) -- 
    this is one of the highest-ROI techniques from industry tools (pdfimages is
    the gold standard for embedded image extraction).
    Falls back to pypdf. Applies our meaningful heuristic for the use-case.
    """
    # Try pdfimages first for best quality extraction
    if _has_pdfimages():
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
                tmp_pdf.write(content)
                pdf_path = Path(tmp_pdf.name)
            out_dir = Path(tempfile.mkdtemp())
            extracted_paths = _extract_images_pdfimages(pdf_path, out_dir)
            images: list[EmbeddedImage] = []
            index = 1
            for img_path in extracted_paths:
                try:
                    data = img_path.read_bytes()
                    if len(data) < MIN_IMAGE_BYTES:
                        continue
                    if not _is_meaningful_image(data, strict=False):
                        continue
                    mime = _guess_mime(data, img_path.name)
                    # Try to infer page from filename (pdfimages uses -<page>-<num>)
                    page = None
                    name_parts = img_path.stem.split("-")
                    if len(name_parts) > 1:
                        try:
                            page = int(name_parts[-2]) if name_parts[-2].isdigit() else None
                        except ValueError:
                            pass
                    images.append(
                        EmbeddedImage(
                            index=index,
                            page=page,
                            data=data,
                            mime_type=mime,
                            image_id=f"img_{index:03d}",
                        )
                    )
                    index += 1
                except Exception:
                    continue
                finally:
                    try:
                        img_path.unlink()
                    except Exception:
                        pass
            try:
                pdf_path.unlink()
                out_dir.rmdir()
            except Exception:
                pass
            if images:
                return images
        except Exception:
            pass  # fall back to pypdf

    # Fallback to pypdf (current approach, enhanced)
    reader = PdfReader(io.BytesIO(content))
    images: list[EmbeddedImage] = []
    index = 1
    for page_number, page in enumerate(reader.pages, start=1):
        for image in page.images:
            if len(image.data) < MIN_IMAGE_BYTES:
                continue
            # Use lenient check here so that image-based pages (scanned docs, slides)
            # have their content images extracted and available for OCR selection.
            # The inspection step (with per-page text awareness) decides whether a page
            # "has images" that should be offered to the user.
            if not _is_meaningful_image(image.data, strict=False):
                continue
            images.append(
                EmbeddedImage(
                    index=index,
                    page=page_number,
                    data=image.data,
                    mime_type=_guess_mime(image.data, image.name),
                    image_id=f"img_{index:03d}",
                )
            )
            index += 1
    return images


def _extract_docx_images(content: bytes) -> list[EmbeddedImage]:
    return [
        EmbeddedImage(
            index=ref.index,
            page=None,
            data=ref.data,
            mime_type=ref.mime_type,
            image_id=ref.image_id,
        )
        for ref in extract_docx_images_ordered(content)
    ]


def _guess_mime(data: bytes, name: str = "") -> str:
    lowered = name.lower()
    if lowered.endswith(".png") or data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if lowered.endswith(".jpg") or lowered.endswith(".jpeg") or data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if lowered.endswith(".gif") or data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if lowered.endswith(".webp") or data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"
