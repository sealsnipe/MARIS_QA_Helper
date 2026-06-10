import io
import json
import zipfile

import pytest

from app.batch_upload import (
    ExtractedDoc,
    BatchFile,
    _validate_plan,
    expand_batch_files,
    plan_kb_entries,
)
from app.llm import LLMResponse
from app.tests.conftest import create_customer, create_user, login
from app.upload import UploadError


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _doc(filename: str, text: str) -> ExtractedDoc:
    return ExtractedDoc(file=BatchFile(key=filename, filename=filename, content=b"", extension=".txt"), text=text)


# --- expand_batch_files -------------------------------------------------


def test_expand_direct_files_keeps_supported_and_skips_rest():
    files, skipped = expand_batch_files(
        [
            ("notes.txt", b"inhalt eins"),
            ("malware.exe", b"nope"),
            ("guide.pdf", b"%PDF-1.4"),
        ]
    )
    assert [f.filename for f in files] == ["notes.txt", "guide.pdf"]
    assert [f.key for f in files] == ["f0", "f2"]
    assert skipped == [{"filename": "malware.exe", "reason": "unsupported_file_type"}]


def test_expand_zip_filters_unsupported_and_hidden_members():
    payload = _zip_bytes(
        {
            "docs/anleitung.md": b"## Anleitung mit Inhalt",
            "docs/setup.exe": b"nope",
            "__MACOSX/._anleitung.md": b"resource fork",
            ".hidden/geheim.txt": b"versteckt",
            "bild.png": b"\x89PNG fake",
        }
    )
    files, skipped = expand_batch_files([("paket.zip", payload)])
    assert [f.filename for f in files] == ["anleitung.md", "bild.png"]
    assert all(f.source_zip == "paket.zip" for f in files)
    assert files[0].key == "f0:docs/anleitung.md"
    assert {s["reason"] for s in skipped} == {"unsupported_file_type"}


def test_expand_zip_skips_nested_zip():
    inner = _zip_bytes({"drin.txt": b"x"})
    payload = _zip_bytes({"a.txt": b"text", "inner.zip": inner})
    files, skipped = expand_batch_files([("outer.zip", payload)])
    assert [f.filename for f in files] == ["a.txt"]
    assert skipped == [{"filename": "outer.zip/inner.zip", "reason": "nested_zip"}]


def test_expand_invalid_zip_raises():
    with pytest.raises(UploadError) as exc:
        expand_batch_files([("kaputt.zip", b"definitiv kein zip")])
    assert exc.value.code == "invalid_zip"


def test_expand_all_unsupported_raises():
    with pytest.raises(UploadError) as exc:
        expand_batch_files([("a.exe", b"x"), ("b.bat", b"y")])
    assert exc.value.code == "no_supported_files"


# --- plan validation / grouping -----------------------------------------


def test_validate_plan_accepts_partition():
    plan = _validate_plan({"entries": [{"files": [0, 2], "title": "a + b"}, {"files": [1], "title": ""}]}, 3)
    assert plan == [{"indices": [0, 2], "title": "a + b"}, {"indices": [1], "title": None}]


def test_validate_plan_rejects_incomplete_or_duplicate():
    assert _validate_plan({"entries": [{"files": [0]}]}, 2) is None
    assert _validate_plan({"entries": [{"files": [0]}, {"files": [0, 1]}]}, 2) is None
    assert _validate_plan({"entries": [{"files": [0, 5]}, {"files": [1]}]}, 2) is None
    assert _validate_plan({"entries": []}, 1) is None


def test_plan_kb_entries_uses_llm_grouping(monkeypatch):
    docs = [_doc("a.txt", "VPN Anleitung"), _doc("b.txt", "VPN Zertifikat"), _doc("c.txt", "Drucker")]

    class FakeLLM:
        def chat(self, messages, tools=None):
            return LLMResponse(
                content='{"entries": [{"files": [0, 1], "title": "VPN + Zertifikat"}, {"files": [2], "title": "Drucker"}]}',
                tool_calls=[],
                assistant_message={},
            )

    monkeypatch.setattr("app.llm.get_llm", lambda db=None: FakeLLM())
    plan = plan_kb_entries(None, docs)
    assert plan == [
        {"indices": [0, 1], "title": "VPN + Zertifikat"},
        {"indices": [2], "title": "Drucker"},
    ]


def test_plan_kb_entries_falls_back_to_singletons(monkeypatch):
    docs = [_doc("a.txt", "x"), _doc("b.txt", "y")]

    def boom(db=None):
        raise RuntimeError("no llm")

    monkeypatch.setattr("app.llm.get_llm", boom)
    assert plan_kb_entries(None, docs) == [{"indices": [0], "title": None}, {"indices": [1], "title": None}]


def test_plan_kb_entries_single_doc_skips_llm():
    assert plan_kb_entries(None, [_doc("a.txt", "x")]) == [{"indices": [0], "title": None}]


# --- API endpoints -------------------------------------------------------


def _login_customer(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})


def test_inspect_batch_endpoint_with_zip(client, db_session):
    _login_customer(client, db_session)
    payload = _zip_bytes({"eins.txt": b"Inhalt eins", "zwei.md": b"Inhalt zwei", "boese.exe": b"x"})
    response = client.post(
        "/api/documents/inspect-batch",
        files=[
            ("files", ("paket.zip", payload, "application/zip")),
            ("files", ("extra.txt", b"Direkter Inhalt", "text/plain")),
        ],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["file_count"] == 3
    names = [doc["filename"] for doc in data["documents"]]
    assert names == ["eins.txt", "zwei.md", "extra.txt"]
    assert data["skipped"][0]["reason"] == "unsupported_file_type"


def test_batch_upload_groups_into_entries(client, db_session, monkeypatch):
    _login_customer(client, db_session)

    class FakeLLM:
        def chat(self, messages, tools=None):
            return LLMResponse(
                content='{"entries": [{"files": [0, 1], "title": "VPN + Zugang"}, {"files": [2], "title": "Drucker einrichten"}]}',
                tool_calls=[],
                assistant_message={},
            )

    monkeypatch.setattr("app.llm.get_llm", lambda db=None: FakeLLM())

    response = client.post(
        "/api/documents/batch",
        files=[
            ("files", ("vpn1.txt", b"VPN Anleitung Teil eins mit genug Inhalt fuer die Indexierung.", "text/plain")),
            ("files", ("vpn2.txt", b"VPN Anleitung Teil zwei mit genug Inhalt fuer die Indexierung.", "text/plain")),
            ("files", ("drucker.txt", b"Drucker einrichten Schritt fuer Schritt mit genug Inhalt.", "text/plain")),
        ],
    )
    assert response.status_code == 200
    data = response.json()
    created = [entry for entry in data["entries"] if entry["status"] == "created"]
    assert len(created) == 2
    assert created[0]["document"]["title"] == "bg-ludwigshafen: VPN + Zugang"
    assert created[0]["filenames"] == ["vpn1.txt", "vpn2.txt"]
    assert created[1]["document"]["title"] == "bg-ludwigshafen: Drucker einrichten"

    docs = client.get("/api/documents").json()["documents"]
    assert len(docs) == 2


def test_batch_upload_never_creates_more_entries_than_files(client, db_session, monkeypatch):
    _login_customer(client, db_session)

    class GreedyLLM:
        def chat(self, messages, tools=None):
            # Ungültig: 3 Einträge aus 2 Dateien -> Fallback auf 1 Eintrag pro Datei
            return LLMResponse(
                content='{"entries": [{"files": [0]}, {"files": [1]}, {"files": [99]}]}',
                tool_calls=[],
                assistant_message={},
            )

    monkeypatch.setattr("app.llm.get_llm", lambda db=None: GreedyLLM())

    response = client.post(
        "/api/documents/batch",
        files=[
            ("files", ("a.txt", b"Erster Inhalt mit ausreichend Laenge fuer die Indexierung.", "text/plain")),
            ("files", ("b.txt", b"Zweiter Inhalt mit ausreichend Laenge fuer die Indexierung.", "text/plain")),
        ],
    )
    assert response.status_code == 200
    created = [entry for entry in response.json()["entries"] if entry["status"] == "created"]
    assert len(created) == 2
    assert created[0]["document"]["title"] == "bg-ludwigshafen: a"


def test_batch_upload_skips_duplicates(client, db_session, monkeypatch):
    _login_customer(client, db_session)
    monkeypatch.setattr("app.llm.get_llm", lambda db=None: (_ for _ in ()).throw(RuntimeError("no llm")))

    content = b"Identischer Inhalt mit ausreichend Laenge fuer die Indexierung."
    first = client.post(
        "/api/documents/batch",
        files=[("files", ("original.txt", content, "text/plain"))],
    )
    assert first.status_code == 200

    second = client.post(
        "/api/documents/batch",
        files=[
            ("files", ("kopie.txt", content, "text/plain")),
            ("files", ("neu.txt", b"Ganz anderer Inhalt mit ausreichend Laenge fuer die Suche.", "text/plain")),
        ],
    )
    assert second.status_code == 200
    data = second.json()
    statuses = {entry["status"] for entry in data["entries"]}
    assert "duplicate" in statuses
    created = [entry for entry in data["entries"] if entry["status"] == "created"]
    assert len(created) == 1
    assert created[0]["filenames"] == ["neu.txt"]


def test_batch_upload_zip_via_admin_route(client, db_session, monkeypatch):
    create_user(db_session, "admin@example.com", "secret123", (), is_admin=True)
    login(client, "admin@example.com", "secret123")
    monkeypatch.setattr("app.llm.get_llm", lambda db=None: (_ for _ in ()).throw(RuntimeError("no llm")))

    payload = _zip_bytes(
        {
            "eins.txt": b"Erster Eintrag aus dem Archiv mit genug Inhalt fuer die Suche.",
            "zwei.txt": b"Zweiter Eintrag aus dem Archiv mit genug Inhalt fuer die Suche.",
        }
    )
    response = client.post(
        "/api/admin/documents/batch",
        files=[("files", ("paket.zip", payload, "application/zip"))],
    )
    assert response.status_code == 200
    data = response.json()
    created = [entry for entry in data["entries"] if entry["status"] == "created"]
    assert len(created) == 2
    assert created[0]["document"]["title"] == "global: eins"
