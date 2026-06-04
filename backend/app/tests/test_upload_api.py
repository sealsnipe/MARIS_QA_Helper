from app.tests.conftest import create_customer, create_user, login


def test_upload_txt_only(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    content = b"Dies ist ein Testdokument mit genug Inhalt fuer die Indexierung."
    response = client.post(
        "/api/documents",
        files={"file": ("notes.txt", content, "text/plain")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["source_type"] == "txt"
    assert payload["document"]["status"] == "indexed"
    assert payload["document"]["title"] == "notes"
    assert payload["document"]["chunk_count"] >= 1


def test_upload_text_only(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    response = client.post(
        "/api/documents",
        data={"title": "Manueller Eintrag", "text": "Dies ist reiner Text mit ausreichend Laenge."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["source_type"] == "manual"
    assert payload["document"]["title"] == "Manueller Eintrag"


def test_upload_combined_text_and_file(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    file_content = b"Dateiinhalt mit genuegend Zeichen fuer die Indexierung."
    response = client.post(
        "/api/documents",
        data={"title": "Kombi-Dokument", "text": "Einleitung aus dem Webformular."},
        files={"file": ("anhang.txt", file_content, "text/plain")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["title"] == "Kombi-Dokument"
    assert payload["document"]["source_type"] == "txt"


def test_upload_unsupported_type(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    response = client.post(
        "/api/documents",
        files={"file": ("bad.exe", b"data", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "unsupported_file_type"


def test_upload_requires_content(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    response = client.post("/api/documents", data={})
    assert response.status_code == 400
    assert response.json()["error"] == "empty_text"


def test_upload_extraction_failure_does_not_persist_document(client, db_session, monkeypatch):
    from app.ingestion import list_documents
    from app.loaders.errors import LoaderError

    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    def fail_load(*_args, **_kwargs):
        raise LoaderError("extraction_failed")

    monkeypatch.setattr("app.upload.load_document", fail_load)
    monkeypatch.setattr(
        "app.upload.inspect_document_path",
        lambda *_args, **_kwargs: type(
            "InspectResult",
            (),
            {
                "has_images": False,
                "image_count": 0,
                "file_type": "pdf",
                "pages_with_images": [],
                "text_extractable": False,
            },
        )(),
    )

    response = client.post(
        "/api/documents",
        files={"file": ("scan.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "extraction_failed"
    assert list_documents(db_session, "bg-ludwigshafen") == []


def test_upload_pdf_with_images_sets_partial_meta(client, db_session, monkeypatch):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    monkeypatch.setattr(
        "app.upload.inspect_document_path",
        lambda *_args, **_kwargs: type(
            "InspectResult",
            (),
            {"has_images": True, "image_count": 2, "file_type": "pdf", "pages_with_images": [1]},
        )(),
    )
    monkeypatch.setattr(
        "app.upload.load_document",
        lambda *_args, **_kwargs: "PDF Text mit genug Inhalt fuer die Indexierung und Extraktion.",
    )
    monkeypatch.setattr("app.upload.save_embedded_images", lambda *_args, **_kwargs: [])

    response = client.post(
        "/api/documents",
        data={"text": "Einleitung mit genug Text fuer die Indexierung."},
        files={"file": ("guide.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert response.status_code == 200
    meta = response.json()["document"]["extraction_meta"]
    assert meta["image_count"] == 2
    assert meta["images_processed"] == 0
    assert meta["coverage"] == "partial"
    assert meta["vision_used"] is False


def test_upload_with_process_images_runs_vision(client, db_session, monkeypatch):
    from app.loaders.vision_ocr import VisionOcrResult

    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    monkeypatch.setattr(
        "app.upload.inspect_document_path",
        lambda *_args, **_kwargs: type(
            "InspectResult",
            (),
            {"has_images": True, "image_count": 1, "file_type": "pdf", "pages_with_images": [1]},
        )(),
    )
    monkeypatch.setattr(
        "app.upload.run_vision_ocr",
        lambda *_args, **_kwargs: VisionOcrResult(
            blocks=['[BILD id="img_001" seite="1"]\nScreenshot Text aus Vision\n[/BILD]'],
            images_processed=1,
            images_failed=0,
            saved_images=[
                __import__("app.document_assets", fromlist=["SavedDocumentImage"]).SavedDocumentImage(
                    id="img_001",
                    filename="img_001.png",
                    page=1,
                    mime_type="image/png",
                )
            ],
        ),
    )
    monkeypatch.setattr(
        "app.upload.load_document",
        lambda *_args, **_kwargs: "PDF Text mit genug Inhalt fuer die Indexierung und Extraktion.",
    )
    monkeypatch.setattr("app.upload.save_embedded_images", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        "app.upload.append_pdf_image_blocks",
        lambda base_text, _path, ocr_result: base_text + "\n\n" + "\n\n".join(ocr_result.blocks),
    )

    response = client.post(
        "/api/documents",
        data={"text": "Einleitung mit genug Text fuer die Indexierung.", "process_images": "true"},
        files={"file": ("guide.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert response.status_code == 200
    meta = response.json()["document"]["extraction_meta"]
    assert meta["vision_used"] is True
    assert meta["images_processed"] == 1
    assert meta["coverage"] == "full"


def test_upload_image_only_pdf_requires_vision(client, db_session, monkeypatch, tmp_path):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    monkeypatch.setattr(
        "app.upload.inspect_document_path",
        lambda *_args, **_kwargs: type(
            "InspectResult",
            (),
            {
                "has_images": True,
                "image_count": 1,
                "file_type": "pdf",
                "pages_with_images": [1],
                "text_extractable": False,
            },
        )(),
    )
    monkeypatch.setattr(
        "app.upload.load_document",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(__import__("app.loaders.errors", fromlist=["LoaderError"]).LoaderError("extraction_failed")),
    )

    response = client.post(
        "/api/documents",
        files={"file": ("scan.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "images_only_requires_vision"


def test_inspect_endpoint(client, db_session, monkeypatch):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    monkeypatch.setattr(
        "app.routes.inspect_upload",
        lambda _db, _customer_id, _content, _filename, prefix_text=None: {
            "has_images": True,
            "image_count": 4,
            "file_type": "docx",
            "pages_with_images": [],
            "text_extractable": True,
            "image_only": False,
            "filename": "guide.docx",
            "duplicate": None,
            "similar": [],
            "content_sha256": None,
        },
    )

    response = client.post(
        "/api/documents/inspect",
        files={"file": ("guide.docx", b"fake", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["has_images"] is True
    assert payload["image_count"] == 4
