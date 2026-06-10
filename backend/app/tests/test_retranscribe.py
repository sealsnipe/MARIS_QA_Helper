import io
import threading
import time

from PIL import Image

from app.loaders.vision_ocr import transcribe_images_pooled
from app.tests.conftest import create_user, login


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color=(40, 90, 200)).save(buffer, format="PNG")
    return buffer.getvalue()


# --- Paralleler OCR-Pool --------------------------------------------------


def test_pooled_transcription_keeps_input_order(monkeypatch):
    def fake_transcribe(image_data, mime_type, *, prompt):
        # Erstes Bild ist am langsamsten — Reihenfolge der Ergebnisse muss trotzdem stimmen.
        index = int(image_data.decode())
        time.sleep(0.05 * (3 - index))
        return f'{{"text": "Bild {index}", "mermaid": null}}'

    monkeypatch.setattr("app.loaders.vision_ocr.transcribe_image", fake_transcribe)
    items = [(str(i).encode(), "image/png") for i in range(3)]
    results = transcribe_images_pooled(items)
    assert results == ["Bild 0", "Bild 1", "Bild 2"]


def test_pooled_transcription_runs_concurrently(monkeypatch):
    lock = threading.Lock()
    active = 0
    max_active = 0

    def fake_transcribe(image_data, mime_type, *, prompt):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return '{"text": "ok", "mermaid": null}'

    monkeypatch.setattr("app.loaders.vision_ocr.transcribe_image", fake_transcribe)
    items = [(b"x", "image/png")] * 8
    progress: list[tuple[int, int]] = []
    results = transcribe_images_pooled(items, on_done=lambda done, total: progress.append((done, total)))
    assert results == ["ok"] * 8
    assert max_active > 1, "Pool soll parallel arbeiten"
    assert max_active <= 4, "Pool ist auf VISION_CONCURRENCY begrenzt"
    assert [entry[0] for entry in progress] == list(range(1, 9))
    assert all(entry[1] == 8 for entry in progress)


def test_pooled_transcription_marks_failures(monkeypatch):
    from app.llm import LLMError

    def fake_transcribe(image_data, mime_type, *, prompt):
        if image_data == b"fail":
            raise LLMError("boom")
        return '{"text": "ok", "mermaid": null}'

    monkeypatch.setattr("app.loaders.vision_ocr.transcribe_image", fake_transcribe)
    results = transcribe_images_pooled([(b"ok", "image/png"), (b"fail", "image/png")])
    assert results == ["ok", None]


# --- Nachverarbeitung über die API ---------------------------------------


def _login_admin(client, db_session):
    create_user(db_session, "admin@example.com", "secret123", (), is_admin=True)
    login(client, "admin@example.com", "secret123")


def _create_image_document(client) -> str:
    response = client.post(
        "/api/admin/documents",
        data={"text": "Begleittext mit ausreichend Laenge fuer die Indexierung des Bildes."},
        files={"file": ("foto.png", _png_bytes(), "image/png")},
    )
    assert response.status_code == 200
    return response.json()["document"]["id"]


def test_retranscribe_open_image_updates_document(client, db_session, monkeypatch):
    _login_admin(client, db_session)
    doc_id = _create_image_document(client)

    detail = client.get(f"/api/admin/documents/{doc_id}").json()
    assert "nicht_verarbeitet" in detail["text"]
    assert detail["images"][0]["transcribed"] is False

    monkeypatch.setattr(
        "app.loaders.vision_ocr.transcribe_image",
        lambda data, mime, *, prompt: '{"text": "Blaues Testbild mit Inhalt", "mermaid": null}',
    )
    token = "retranscribe-progress-12345"
    response = client.post(
        f"/api/admin/documents/{doc_id}/transcribe-images",
        json={"image_ids": ["img_001"], "progress_token": token},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["processed"] == ["img_001"]
    assert payload["failed"] == []
    assert payload["document"]["extraction_meta"]["coverage"] == "full"
    assert payload["document"]["extraction_meta"]["images_processed"] == 1

    detail = client.get(f"/api/admin/documents/{doc_id}").json()
    assert "nicht_verarbeitet" not in detail["text"]
    assert "Blaues Testbild mit Inhalt" in detail["text"]
    assert detail["images"][0]["transcribed"] is True

    progress = client.get(f"/api/documents/batch-progress/{token}")
    assert progress.status_code == 200
    assert progress.json()["percent"] == 100


def test_retranscribe_rejects_already_transcribed(client, db_session, monkeypatch):
    _login_admin(client, db_session)
    doc_id = _create_image_document(client)
    monkeypatch.setattr(
        "app.loaders.vision_ocr.transcribe_image",
        lambda data, mime, *, prompt: '{"text": "Inhalt", "mermaid": null}',
    )
    first = client.post(f"/api/admin/documents/{doc_id}/transcribe-images", json={"image_ids": ["img_001"]})
    assert first.status_code == 200

    second = client.post(f"/api/admin/documents/{doc_id}/transcribe-images", json={"image_ids": ["img_001"]})
    assert second.status_code == 400
    assert second.json()["error"] == "no_images_selected"


def test_retranscribe_unknown_document_returns_404(client, db_session):
    _login_admin(client, db_session)
    response = client.post(
        "/api/admin/documents/00000000-0000-0000-0000-000000000000/transcribe-images",
        json={"image_ids": ["img_001"]},
    )
    assert response.status_code == 404


def test_retranscribe_failed_ocr_keeps_placeholder(client, db_session, monkeypatch):
    from app.llm import LLMError

    _login_admin(client, db_session)
    doc_id = _create_image_document(client)
    monkeypatch.setattr(
        "app.loaders.vision_ocr.transcribe_image",
        lambda data, mime, *, prompt: (_ for _ in ()).throw(LLMError("boom")),
    )
    response = client.post(f"/api/admin/documents/{doc_id}/transcribe-images", json={"image_ids": ["img_001"]})
    assert response.status_code == 502
    assert response.json()["error"] == "vision_failed"

    detail = client.get(f"/api/admin/documents/{doc_id}").json()
    assert "nicht_verarbeitet" in detail["text"]
