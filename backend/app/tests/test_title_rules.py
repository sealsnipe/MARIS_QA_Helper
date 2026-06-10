from app.llm import LLMResponse
from app.upload import TITLE_KEYWORDS_PROMPT, _apply_title_rule, generate_title_keywords
from app.tests.conftest import create_customer, create_user, login


class FakeTitleLLM:
    def __init__(self, content: str | None) -> None:
        self.content = content
        self.messages: list[dict] | None = None

    def chat(self, messages, tools=None) -> LLMResponse:
        self.messages = messages
        return LLMResponse(content=self.content, tool_calls=[], assistant_message={})


def test_apply_title_rule_prepends_kuerzel() -> None:
    assert _apply_title_rule("kkrr", "VPN Setup") == "kkrr: VPN Setup"


def test_apply_title_rule_keeps_existing_kuerzel() -> None:
    assert _apply_title_rule("kkrr", "kkrr: VPN Setup") == "kkrr: VPN Setup"
    assert _apply_title_rule("kkrr", "KKRR: VPN Setup") == "KKRR: VPN Setup"


def test_apply_title_rule_truncates_to_200() -> None:
    assert len(_apply_title_rule("kkrr", "x" * 300)) == 200


def test_generate_title_keywords_parses_plus_separated(monkeypatch) -> None:
    fake = FakeTitleLLM("VPN-Zugang + Zertifikat erneuern + Windows 11")
    monkeypatch.setattr("app.llm.get_llm", lambda db=None: fake)
    result = generate_title_keywords(None, "Anleitung zum Erneuern des VPN-Zertifikats unter Windows 11.")
    assert result == "VPN-Zugang + Zertifikat erneuern + Windows 11"
    assert fake.messages is not None
    assert fake.messages[0]["content"] == TITLE_KEYWORDS_PROMPT


def test_generate_title_keywords_caps_at_five(monkeypatch) -> None:
    fake = FakeTitleLLM("a + b + c + d + e + f + g")
    monkeypatch.setattr("app.llm.get_llm", lambda db=None: fake)
    assert generate_title_keywords(None, "Genug Inhalt fuer eine Titelgenerierung.") == "a + b + c + d + e"


def test_generate_title_keywords_handles_llm_failure(monkeypatch) -> None:
    def boom(db=None):
        raise RuntimeError("no backend")

    monkeypatch.setattr("app.llm.get_llm", boom)
    assert generate_title_keywords(None, "Genug Inhalt fuer eine Titelgenerierung.") is None


def test_generate_title_keywords_empty_response(monkeypatch) -> None:
    fake = FakeTitleLLM("")
    monkeypatch.setattr("app.llm.get_llm", lambda db=None: fake)
    assert generate_title_keywords(None, "Genug Inhalt fuer eine Titelgenerierung.") is None


def test_upload_without_title_uses_generated_keywords(client, db_session, monkeypatch):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    monkeypatch.setattr(
        "app.upload.generate_title_keywords",
        lambda _db, _text: "Thema Eins + Thema Zwei",
    )
    content = b"Dies ist ein Testdokument mit genug Inhalt fuer die Indexierung."
    response = client.post(
        "/api/documents",
        files={"file": ("notes.txt", content, "text/plain")},
    )
    assert response.status_code == 200
    assert response.json()["document"]["title"] == "bg-ludwigshafen: Thema Eins + Thema Zwei"


def test_upload_without_title_falls_back_to_filename(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    # conftest stubs generate_title_keywords to None -> filename stem with kuerzel prefix
    content = b"Dies ist ein Testdokument mit genug Inhalt fuer die Indexierung."
    response = client.post(
        "/api/documents",
        files={"file": ("handbuch.txt", content, "text/plain")},
    )
    assert response.status_code == 200
    assert response.json()["document"]["title"] == "bg-ludwigshafen: handbuch"
