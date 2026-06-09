# Review & Implementationsplan — 2026-06-09

**Status:** ERLEDIGT (alle 7 Aufgaben umgesetzt, einzeln committed, Tests+Tenant+Doku-Spiegel grün nach jeder; Datei nach _old verschoben)
**Basis:** HEAD `b5608af` auf `main`, Testlauf `cd backend && PYTHONPATH=. python3 -m pytest` → **4 failed, 180 passed** (am Ende 0 failed / 189+ passed)
**Reviewer:** Claude (automatisiertes Projekt-Review, Read-only)
**Verbindliche Regeln:** `docs/PROJECT_STANDARDS.md`, `docs/DOCUMENTATION_RULES.md` (Doku-Spiegel pflegen!), `docs/13_coding_agent_brief.md`

---

## Teil 1 — Review-Ergebnis

### Was gut ist (nicht anfassen)

- **Tenant-Isolation** ist sauber: `customer_id` ausschließlich serverseitig aus Session (`tenant.py:get_current_customer`), `user_has_customer`-Check, physisch getrennte Qdrant-Collections pro Kunde. Dedizierter Pflichttest `test_tenant_isolation.py` grün.
- Security-Basis stimmt: Argon2-Hashing, `request.session.clear()` beim Login (Session-Fixation), `SameSite=Lax`, `secrets.compare_digest` für Token-Vergleich, zentrale Exception-→-JSON-Handler in `main.py`.
- Testkultur: 33 Test-Dateien, 184 Tests, alles ohne Netz (Mocks in `conftest.py`).

### Findings (nach Priorität)

#### F1 — 4 rote Tests: Bildheuristik verschärft ohne Testanpassung (KRITISCH)

`python3 -m pytest` schlägt auf sauberem HEAD fehl:

- `test_image_inspect.py::test_inspect_docx_with_image`
- `test_image_inspect.py::test_inspect_standalone_png`
- `test_image_inspect.py::test_inspect_upload_png_has_preview`
- `test_selective_vision.py::test_inspect_upload_returns_image_previews`

Ursache: Die Commits `8ace6cf`/`32ec578`/`b5608af` haben `MIN_IMAGE_BYTES = 1024` und `_is_meaningful_image` verschärft. `_inspect_image_file` (`backend/app/loaders/image_inspect.py:259-273`) filtert jetzt auch **eigenständig hochgeladene Bilddateien** unter 1024 Bytes weg — das einfarbige 220×220-Test-PNG hat nur 664 Bytes. Gleiches Problem bei den DOCX-Tests (einfarbige Mini-Bilder als Fixture, gefiltert in `_inspect_docx`, Zeile 248).

**Fachliche Bewertung:** Der Byte-Filter ist für *eingebettete* PDF/DOCX-Bilder sinnvoll (Hintergründe, Deko). Für eine **vom User explizit als Datei hochgeladene PNG/JPG** ist er falsch — die ist immer gewollter Inhalt.

#### F2 — Integration-API-Token: Admin-UI-Wert wird nie geprüft (BUG, Security/Korrektheit)

- Admin-UI schreibt das Token in die DB: `routes.py:1940` → `update_secret(db, "integration_api_token", …)`.
- Status-Anzeige liest es per `get_effective_secret` (`secrets_admin.py:101`, `llm_presets.py:367`) und zeigt „enabled".
- Die **eigentliche Auth** in `integration_auth.py:41-50` prüft aber nur `settings.INTEGRATION_API_TOKEN` aus dem ENV (`settings.integration_enabled` ebenso).

Folge: Ein über die UI gesetztes oder rotiertes Token wird nie akzeptiert; ein altes ENV-Token bleibt gültig, obwohl die UI etwas anderes anzeigt.

#### F3 — pdfimages-Integration (Commit `b5608af`) ist größtenteils inert (toter Code)

1. In `_inspect_pdf` (`image_inspect.py:191-203`) werden `pdfimages_info` und `images_by_page` berechnet und **nie verwendet**. Es wird nur eine Temp-PDF geschrieben und wieder gelöscht — reiner Overhead pro Inspektion.
2. Size-Parsing in `_list_pdf_images_pdfimages` (`image_inspect.py:56`) liest die falsche Spalte: bei `pdfimages -list` ist `parts[10]` die Objekt-ID, die Größe steht in Spalte 14 (`size`). Aktuell folgenlos, weil ungenutzt.
3. `backend/Dockerfile` installiert **kein `poppler-utils`** → in der Docker-Produktion existiert `pdfimages` nicht. Der einzige echte Nutzer (`vision_ocr.py:294-311`) fällt dort immer auf den pypdf-Fallback zurück.

#### F4 — Interne Fehlerdetails leaken an API-Clients (NIEDRIG)

Der generische Handler `main.py:204-215` gibt `{"error": "internal_error", "detail": str(exc)}` zurück — leakt Pfade/SQL-Fehlertexte. Für ein internes Tool vertretbar, hinter öffentlichem Proxy nicht.

#### F5 — Kein Rate-Limiting am Login (NIEDRIG)

`POST /login` (`routes.py:433`) erlaubt unbegrenzte Versuche. Argon2 bremst, aber ein simples In-Memory-Limit (z. B. 10 Fehlversuche/Minute pro IP+E-Mail) wäre angemessen.

#### F6 — Strukturschulden (KEIN Refactor in diesem Zyklus, nur dokumentieren)

- `routes.py`: 2.197 Zeilen, 100 Routen. `app.js`: 4.614 Zeilen. `app.css`: 3.561 Zeilen. Gate-A-Entscheidung aus dem Review 2026-06-05 bleibt bestehen: kein Refactor, solange Tests grün und Delegation sauber. Bei nächstem größerem Feature: Domänen-Router (`APIRouter`) erwägen.
- `InMemoryVectorStore.copy_collection` (`qdrant_store.py:265-278`) **verschiebt** (poppt die alte Collection), während `QdrantVectorStore.copy_collection` echt kopiert — Test-Double weicht semantisch von Produktion ab.
- Dockerfile dupliziert die Dependency-Liste aus `pyproject.toml` (Drift hat schon einmal zugeschlagen: `cc37fbd` „missing Pillow"). Außerdem landet `pytest` im Prod-Image.
- Kein CI. Genau das hat F1 und die Regressionen `e5636c0`/`855a1a6`/`d3a6725` durchgelassen.
- API-Keys/OAuth-Tokens liegen im Klartext in SQLite (`AppSecret`, `LlmPreset.oauth_token`). Für Self-Hosting akzeptabel — als bewusste Entscheidung in `docs/07_auth_and_security.md` festhalten.

---

## Teil 2 — Implementationsplan

Reihenfolge ist verbindlich (Aufgabe 1 macht die Suite grün, alles Weitere baut darauf auf). Jede Aufgabe einzeln committen. Nach jeder Aufgabe: kompletter Testlauf `cd backend && PYTHONPATH=. python3 -m pytest -q` muss grün sein.

### Aufgabe 1 — Rote Tests fixen (F1)

**Entscheidung (so umsetzen):** Standalone-Bilddateien vom Byte-Filter ausnehmen; für eingebettete Bilder die Test-Fixtures realistisch machen.

1. In `_inspect_image_file` (`image_inspect.py`): den `MIN_IMAGE_BYTES`-Check **entfernen**. Stattdessen nur prüfen, ob PIL die Datei öffnen kann (`PILImage.open` + `verify()`); nicht dekodierbare Dateien → `has_images=False`. Eine valide, vom User hochgeladene Bilddatei zählt immer als Bild.
2. Prüfen, ob `upload.py` für Standalone-Bilder denselben Filter dupliziert (`grep -n MIN_IMAGE_BYTES backend/app/upload.py`) — falls ja, dort konsistent anpassen.
3. Test-Fixtures in `test_image_inspect.py` und `test_selective_vision.py` für **eingebettete** DOCX-Bilder realistisch machen: statt einfarbiger Flächen ein Rauschbild erzeugen (z. B. `Image.frombytes` mit `os.urandom`-Pixeln, ≥200×200 → komprimiert sicher >1 KB und besteht `_is_meaningful_image`). Die Absicht der Tests (Bild wird erkannt) unverändert lassen.
4. Falls ein Test danach gezielt das Filterverhalten dokumentieren soll: einen neuen Test ergänzen „einfarbiges Mini-Bild eingebettet in DOCX wird gefiltert" — damit ist das Verhalten explizit statt zufällig.

**Akzeptanz:** Alle 184+ Tests grün. Standalone-PNG <1 KB wird als Bild erkannt; eingebettetes Deko-Bild wird weiterhin gefiltert.

### Aufgabe 2 — Integration-Token aus DB prüfen (F2)

In `backend/app/integration_auth.py`:

1. `get_integration_user`: statt `settings.INTEGRATION_API_TOKEN` →
   `expected = get_effective_secret(db, "integration_api_token") or ""` (Import aus `app.secrets_admin`; `db` ist als Dependency schon da).
2. „Enabled"-Check ebenfalls auf den effektiven Wert stützen: `if not expected.strip(): raise IntegrationDisabledError()`. Die Property `settings.integration_enabled` wird dann hier nicht mehr benutzt (in `config.py` belassen, andere Nutzer prüfen).
3. Achtung Zirkularimport: `secrets_admin` importiert nichts aus `integration_auth` — direkter Top-Level-Import ist safe (vorher mit `grep` verifizieren).
4. Tests in `test_integration_api.py` erweitern:
   - Token nur in DB gesetzt (via `update_secret`) → Request mit diesem Token: 200.
   - Token in DB rotiert → altes ENV-Token: 401.
   - DB-Override auf leer („disable") → 503 `integration_disabled`, auch wenn ENV gesetzt ist (das ist die dokumentierte „override to empty"-Semantik aus `secrets_admin.py:53`).
5. Doku-Spiegel aktualisieren: `docs/system/12_integration_api.md` + `docs/docs/backend/app/integration_auth.md` (Quelle der Wahrheit: DB-Secret mit ENV-Fallback).

**Akzeptanz:** Über die Admin-UI gesetztes Token funktioniert sofort gegen `/api/integration/*`; Statusanzeige und tatsächliche Auth sind konsistent.

### Aufgabe 3 — pdfimages aufräumen (F3)

1. **Toten Code entfernen:** In `_inspect_pdf` den kompletten pdfimages-Block (Temp-Datei, `_list_pdf_images_pdfimages`-Aufruf, `images_by_page`) streichen — die pypdf-Schleife mit `_is_meaningful_image` bleibt die alleinige Inspektionslogik. **Nicht** versuchen, die Metadaten „doch noch zu nutzen" — kein Mehrwert für die Inspektion, nur für die Extraktion (und die läuft in `vision_ocr.py` bereits).
2. `_list_pdf_images_pdfimages` ersatzlos löschen, wenn danach ungenutzt (mit `grep` verifizieren). `_has_pdfimages` und `_extract_images_pdfimages` bleiben (Nutzer: `vision_ocr.py`).
3. **Dockerfile:** `RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils && rm -rf /var/lib/apt/lists/*` ergänzen, damit der Qualitätspfad in `vision_ocr.py` in Docker überhaupt aktiv ist.
4. `docs/docs/backend/Dockerfile.md` und `docs/docs/backend/app/loaders/`-Spiegel (falls vorhanden) nachziehen; `docs/11_setup_and_operations.md` um den Hinweis ergänzen, dass `poppler-utils` optional ist (Fallback: pypdf) und für lokale Dev-Umgebung per apt installierbar.

**Akzeptanz:** Keine Temp-PDF mehr pro Inspektion; `pdfimages` im Docker-Image vorhanden; Tests grün (die Inspektionstests dürfen sich nicht ändern, da der Block ohnehin wirkungslos war).

### Aufgabe 4 — Fehlerdetails nicht mehr leaken (F4)

In `main.py:unhandled_exception_handler`: `detail` nur noch loggen, Response auf `{"error": "internal_error"}` reduzieren. Damit das Frontend debugbar bleibt: eine kurze Request-ID generieren (`uuid4().hex[:8]`), in Log und Response (`"ref": …`) aufnehmen. Frontend (`app.js`) zeigt bei `internal_error` ggf. die `ref` an — prüfen, ob irgendwo `detail` von `internal_error` geparst wird (`grep -n "internal_error" backend/app/static/app.js`).

**Akzeptanz:** Kein `str(exc)` mehr in 500er-Responses; Log enthält Traceback + ref.

### Aufgabe 5 — Login-Rate-Limit (F5)

Minimal halten, keine neue Dependency: In-Memory-Dict in `routes.py` (oder kleines Modul `app/login_throttle.py`): Schlüssel `(client_ip, normalized_email)`, Sliding Window 60 s, max. 10 Fehlversuche, danach Redirect `/login?error=rate_limited` (Login-Template um die Meldung ergänzen). Erfolgreicher Login resettet den Zähler. Bei `--workers 1` (siehe Dockerfile CMD) ist In-Memory ausreichend — als Annahme im Code-Kommentar festhalten. Tests: 11. Fehlversuch → rate_limited; nach Erfolg wieder frei.

### Aufgabe 6 — CI einrichten (F6, verhindert Wiederholung von F1)

`.github/workflows/test.yml`: bei Push/PR auf `main` → Python 3.12, `pip install -e backend` (bzw. die pyproject-Dependencies), dann `cd backend && PYTHONPATH=. python3 -m pytest -q`. Tests laufen ohne Netz (Mocks), also kein Secret nötig. Optional zweiter Job mit Docker-Build als Smoke-Test.

**Akzeptanz:** Workflow läuft grün auf dem PR dieser Änderungen.

### Aufgabe 7 — Dokumentations-Nachträge (F6, nur Doku)

1. `docs/07_auth_and_security.md`: Abschnitt „Secrets at rest" — Klartext in SQLite ist bewusste Entscheidung (Self-Hosting, Dateisystemrechte), Risiko + Mitigation (Backup-Verschlüsselung) benennen.
2. `docs/15_implementation_status.md`: dieses Review + umgesetzte Aufgaben vermerken.
3. Bekannte Abweichung `InMemoryVectorStore.copy_collection` (move statt copy) entweder **fixen** (Kopie der Buckets statt `pop`, ~5 Zeilen, dann Mini-Test) oder in `docs/system/10_testing_landscape.md` als Known Difference dokumentieren. Fixen ist vorzuziehen.

### Explizit NICHT in diesem Zyklus (nicht anfangen)

- Kein Split von `routes.py` / `app.js` / `app.css` (Gate A).
- Keine Alembic-Migrationen (handgerollte `_migrate_schema` reicht für SQLite-Scale).
- Keine Verschlüsselung der DB-Secrets.
- Kein Umbau des Dockerfiles auf `pip install .` (nur poppler-utils ergänzen; Dedup der Dependency-Liste ist ein eigener, späterer Task).

---

## Abschluss-Checkliste für den Coder

- [x] Alle Aufgaben einzeln committed, Commit-Messages nach bisherigem Stil
- [x] `cd backend && PYTHONPATH=. python3 -m pytest -q` → 0 failed
- [x] `pytest app/tests/test_tenant_isolation.py -q` explizit grün (Pflicht laut PROJECT_STANDARDS)
- [x] Doku-Spiegel gemäß `DOCUMENTATION_RULES.md` für jede geänderte Datei aktualisiert
- [x] Diese Datei nach `docs/orchestration/_old/2026-06-09-review-und-implementationsplan.md` verschieben und Status oben auf ERLEDIGT setzen
