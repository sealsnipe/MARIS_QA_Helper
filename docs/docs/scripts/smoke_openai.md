# `scripts/smoke_openai.py`

**Quellpfad:** `scripts/smoke_openai.py`

## Zweck und logischer Aufbau

Manueller **Connectivity-Check** für OpenAI **Platform API**: ein Embedding-Call und ein Chat-Completion mit Settings aus `.env`. Erkennt Platzhalter-Keys und nutzt bei Chat-Fehler Fallback-Modell `gpt-4o-mini`.

Kein argparse — direkter `main()`-Einstieg.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `openai.OpenAI`; `app.config.get_settings`
- **Wird genutzt von:** manuell; empfohlen in `setup_env.py`-Ausgabe
- **HTTP:** `settings.OPENAI_BASE_URL` (Embeddings + Chat)
- **Env:** `OPENAI_API_KEY`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`, `CHAT_MODEL`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `ROOT` | `Path` | Repo-Root (`backend` auf `sys.path`) |
| `FALLBACK_CHAT_MODEL` | `str` | `gpt-4o-mini` |
| `PLACEHOLDER_KEY` | `str` | `sk-placeholder-replace-me` |

## Funktionen und Klassen

### `_ensure_real_key(api_key: str) -> None`

**Beschreibung:** Bricht ab bei leerem oder Platzhalter-Key; verweist auf `setup_env.py`.

---

### `_test_embedding(client: OpenAI, model: str, dim: int) -> list[float]`

**Beschreibung:** `embeddings.create` mit Test-String; prüft Vektorlänge gegen `EMBEDDING_DIM`.

---

### `_test_chat(client: OpenAI, model: str) -> tuple[str, str]`

**Beschreibung:** Kurze Chat-Completion; User fordert exakt „OK“; `max_tokens=8`.

---

### `main() -> None`

**Beschreibung:** `get_settings.cache_clear()`; baut `OpenAI`-Client; druckt Base URL und Modelle; führt Embedding dann Chat aus (mit Fallback-Pfad).

**Aufrufer / Aufgerufene:** `_ensure_real_key`, `_test_embedding`, `_test_chat`.
