# Dokumentationsregeln — MARIS Q/A Helper

**Stand:** 2026-06-05 (Review-Sync) 
**Status:** verbindlich für neue und überarbeitete Doku  
**Erweiterbar:** ja — weitere Kapitel (Architektur-Overviews, ADRs, Runbooks) kommen später ergänzend dazu

---

## 1. Zwei Ebenen der Dokumentation

| Ebene | Ort | Zweck |
|---|---|---|
| **Planung & Produkt** | `docs/01_…md` … `docs/15_…md`, `docs/DEPLOY.md` | Vision, Anforderungen, Architektur, API-Spec, Betrieb — **thematisch**, nicht dateiweise |
| **Code-Spiegel (file-per-file)** | `docs/docs/…` | **Eine Markdown-Datei pro Quellcode-Datei** — Symbole, Traces, logischer Aufbau |
| **System / Querschnitt** | `docs/system/…` | **End-to-End**, Mandant, Pipelines, Betrieb — **dateiübergreifend** |

Dieses Dokument regelt **primär die file-per-file-Ebene** unter `docs/docs/`.  
Querschnitt: siehe **`docs/system/00_README.md`**. Planungsdocs verweisen bei Bedarf auf Spiegel und System-Docs.

---

## 2. Spiegelregel (Pfad-Mapping)

Jede dokumentierte Quelldatei im Repository bekommt **genau eine** Markdown-Datei:

```
<repo-root>/<pfad>/<name>.<ENDUNG>
    →
docs/docs/<pfad>/<name>.md
```

**Beispiele**

| Quelle | Doku |
|---|---|
| `backend/app/routes.py` | `docs/docs/backend/app/routes.md` |
| `scripts/dev_local.sh` | `docs/docs/scripts/dev_local.md` |
| `docker-compose.yml` | `docs/docs/docker-compose.md` |
| `README.md` (Root) | `docs/docs/README.md` |
| `.env.example` | `docs/docs/.env.example.md` |

**Regeln**

- Ordnerstruktur unter `docs/docs/` **1:1** wie im Repo (ab Root).
- Endung wird **immer** `.md`, unabhängig von `.py`, `.sh`, `.html`, `.yml`, …
- Dateiname ohne Endung bleibt identisch (`app.js` → `app.md`, nicht `app.js.md`).
- Sonderfall Doppel-Endung: `.env.example` → `.env.example.md` (nicht `.env.md`).

---

## 3. Welche Dateien dokumentiert werden

### 3.1 Immer dokumentieren

- Python unter `backend/app/` (Module, Loader, Tests)
- Frontend: `backend/app/static/*` (eigene Dateien), `backend/app/templates/*`
- Shell-Skripte: `install.sh`, `setup.sh`, `scripts/*.sh`
- Python-Hilfsskripte unter `scripts/` (Seed, Setup, Smoke, …)
- Docker / Compose: `docker-compose*.yml`, `backend/Dockerfile`
- Konfigurationsvorlagen: `.env.example`, `.env.dev.example`, `qdrant.yaml`, `backend/pyproject.toml`
- Root-`README.md`

### 3.2 Kurz dokumentieren (siehe Abschnitt 6)

- Reine **Betriebs-/Install-Skripte** ohne Fachlogik (`start.sh`, `stop.sh`, `restart.sh`, …)
- **Third-Party-Vendor** unter `static/vendor/` (nur Herkunft + Zweck im UI)
- **Statische Assets** ohne Logik (SVG-Logos)

### 3.3 Nicht spiegeln

- Laufzeitdaten: `data-dev/`, `storage/`, `backend/data/uploads/`
- Git, Caches, Virtualenvs: `.git/`, `__pycache__/`, `.pytest_cache/`, `.venv/`
- Geheimnisse: `.env`, `.env.dev` (nur `.example`-Varianten dokumentieren)
- Binär- oder generierte Artefakte ohne Quellcharakter

---

## 4. Sprache und Stil

- **Fließtext:** Deutsch
- **Symbolnamen, Pfade, HTTP-Routen, Env-Keys, JSON-Felder:** exakt wie im Code (Englisch)
- **Ton:** sachlich, präzise, für Entwickler die das Repo nicht kennen
- **Keine** wörtliche Wiederholung des gesamten Quellcodes — beschreiben, nicht kopieren
- Docstrings aus dem Code **dürfen** übernommen oder gekürzt werden, wenn sie korrekt sind

---

## 5. Vollständige Vorlage — Fachlogik & Anwendungscode

Gilt für alles, was **Projektlogik** trägt: FastAPI-Module, Agent/RAG, Ingestion, Auth, Mandanten, UI-JS, Templates mit fachlichem Verhalten, Seed-Skripte mit DB-Logik, Tests.

Jede Spiegel-Datei **muss** diese Abschnittsreihenfolge haben:

```markdown
# `<relativer/pfad/datei.ext>`

**Quellpfad:** `<relativer/pfad/datei.ext>`

## Zweck und logischer Aufbau

(2–6 Absätze oder nummerierte Gliederung)
- Wofür existiert die Datei im Gesamtsystem?
- In welcher Reihenfolge liest man den Code (Imports → Konstanten → Hilfsfunktionen → öffentliche API)?
- Welche Rolle spielt sie im Request-/Datenfluss?

## Abhängigkeiten und Traces

Bullet-Liste, gruppiert nach Richtung:

- **Importiert / nutzt:** andere Projektdateien, externe Libraries
- **Wird genutzt von:** Aufrufer (Module, Routes, Tests, Skripte, Templates, `app.js`)
- **HTTP / UI / CLI:** relevante Endpoints, Template-IDs, Shell-Aufrufe
- **Daten:** SQLite-Tabellen, Qdrant-Collections, Dateisystem-Pfade

Nur **projektrelevante** Traces — keine Standard-Library ohne Bezug.

## Konstanten, Typen und Modulebene

Für **jedes** Symbol auf Modulebene:

| Name | Art | Beschreibung |
|---|---|---|
| `FOO` | Konstante | … |
| `MyError` | Exception-Klasse | … |
| `Settings` | Pydantic-Model | … |

Ausnahme: triviale Re-Exports in `__init__.py` — eine Zeile pro Export reicht.

## Funktionen und Klassen

### `funktionsname(param1, param2) -> Rückgabe`

**Beschreibung:** Was tut die Funktion in einem Satz?

**Parameter / Rückgabe:** Kurz pro Parameter und Rückgabewert.

**Ablauf / lokale Variablen:** Nur **nicht-triviale** Locals benennen und erklären  
(z. B. `merged`, `store`, `params`, `stmt` — nicht jede Schleifenvariable).

**Aufrufer / Aufgerufene:** Verweise auf andere Symbole oder Dateien.

---

### Klassen

Zuerst die Klasse selbst, dann **jede Methode** im gleichen Unterformat wie Funktionen.  
Klassenattribute (`Mapped[…]`, Instanzfelder) in einer Tabelle unter der Klassenbeschreibung.

## (Optional) HTML / JS / CSS — zusätzliche Hinweise

- **Templates:** Blocks, `extends`, wichtige Element-IDs, angebundene JS-Init-Funktion
- **app.js:** Page-Boot (`APP_BOOT.page`), Event-Delegation, API-Pfade
- **app.css:** CSS-Variablen-Block, Komponenten-Sektion — nur wenn für die Datei relevant

## (Optional) Tests

Bei `test_*.py` zusätzlich kurz:

- **Fixtures** aus `conftest.py`, die diese Datei nutzt
- **Abgedecktes Modul** und Intent pro Testfunktion (`test_foo_bar`: erwartetes Verhalten)
```

### 5.1 Vollständigkeitsanspruch

In Fachlogik-Dateien **alle** benannten Definitionen erfassen:

- Module-Konstanten und Regex
- Klassen, Dataclasses, Protocols, TypedDicts, Pydantic-Models
- Funktionen und async-Funktionen (öffentlich **und** privat mit `_`-Prefix)
- Methoden inkl. `@property`, `@classmethod`, `@staticmethod`
- Wichtige innerhalb von Funktionen gesetzte Variablen (siehe oben)
- Route-Handler in `routes.py` (als Funktionen behandeln)
- IIFE-Abschnitte und `init*Page`-Funktionen in `app.js`

**Nicht** auflisten: reine Import-Zeilen, leere `__init__.py` ohne Logik.

---

## 6. Kurz-Vorlage — Skripte, Ops, Config, Vendor

Für Dateien **ohne** oder mit **minimaler** Fachlogik:

```markdown
# `<pfad/datei>`

**Quellpfad:** `<pfad/datei>`

## Zweck

1–3 Sätze: Wofür ist die Datei da, wann führt man sie aus?

## Ablauf (kurz)

- nummerierte Schritte oder Stichpunkte
- welche anderen Skripte / Compose-Services / Tools aufgerufen werden

## Konfiguration / Parameter

Env-Variablen, CLI-Args, Compose-Services — tabellarisch oder als Liste.

## Siehe auch

Links auf verwandte Spiegel-Dateien oder Planungsdocs (`docs/11_setup_and_operations.md`).
```

**Kurz-Doku reicht für:** `install.sh`, `setup.sh`, `scripts/start.sh`, `stop.sh`, `restart.sh`, `update.sh`, `monitor_deploy.sh`, `compose_env.sh`, Vendor-Minified-JS, reine SVG-Assets.

**Volle Doku trotzdem**, wenn ein Skript substantielle Logik enthält (z. B. `seed_customers.py`, `dev_local.sh` mit Qdrant-Start, `routes.py`).

---

## 7. Pflege und Qualität

| Regel | Detail |
|---|---|
| **Quelle der Wahrheit** | Immer der Code im Repo — Doku bei Code-Änderung mitziehen |
| **Keine erfundenen APIs** | Endpoints und Symbole nur dokumentieren, wenn sie existieren |
| **Broken links vermeiden** | Traces als relative Pfade: `` `backend/app/foo.py` `` oder Link auf `docs/docs/.../foo.md` |
| **Duplikate** | Fachliche Architektur nicht in jeder Spiegel-Datei wiederholen — auf Planungsdocs verweisen |
| **Neue Datei** | Neue Quellcode-Datei → neue Spiegel-`.md` im selben PR / derselben Änderung |
| **Gelöschte Datei** | Spiegel-`.md` löschen oder als „entfernt“ in Changelog vermerken |

---

## 8. Index

- **Regelwerk:** `docs/DOCUMENTATION_RULES.md`
- **Projekt-Standards:** `docs/PROJECT_STANDARDS.md` (Prioritäten, Refactoring-Gate, Doku-Pflicht)
- **Spiegel-Index (Dateibaum):** `docs/docs/INDEX.md` — wird mit den Spiegel-Dateien gepflegt
- Root-`README.md`-Spiegel: `docs/docs/README.md` (Inhalt = Projekt-README, kein Dateiindex)
- Planungs-Einstieg: `docs/README.md` (verweist auf PROJECT_STANDARDS)

---

## 9. Checkliste vor „fertig“ (file-per-file)

- [ ] Pfad unter `docs/docs/` entspricht Spiegelregel (Abschnitt 2)
- [ ] Abschnitt **Zweck und logischer Aufbau** vorhanden
- [ ] **Traces** in beide Richtungen (nutzt / wird genutzt von)
- [ ] Alle relevanten Symbole tabelliert oder unter Überschriften
- [ ] Bei Funktionen: Parameter, Rückgabe, wichtige Locals, Aufrufkette
- [ ] Skript vs. Fachlogik: richtige Vorlage (Abschnitt 5 vs. 6)
- [ ] Deutsch, Bezeichner im Original

---

## 10. Spätere Erweiterungen (Platzhalter)

Erledigt (2026-06-03 + Review 2026-06-05):

- **Ebene 3 Querschnitt:** `docs/system/00_README.md` … `11_operations_runbook.md`
- **Ist-Stand:** `docs/15_implementation_status.md`
- **Einheitlicher Einstieg + Gate:** `docs/PROJECT_STANDARDS.md`
- **Vollständige Spiegel:** 25 fehlende nachgezogen (Review); `docs/docs/INDEX.md` + `system/09` + `03 §7` sync
- Review-Ergebnis: `docs/reviews/2026-06-05-project-review.md` (A: kein Refactor)

Noch offen:

- ADR-Prozess und Ablage
- Automatische Doc-Generierung / CI-Check „Code-Datei ohne Spiegel-`.md`“
- Changelog-Konvention zwischen Planungs- und Spiegel-Doku

Bei Erweiterung dieses Dokuments: neue Abschnitte nummerieren, Datum oben anpassen.

---

## 11. Querschnitts-Dokumente (Ebene 3) — Kurzregeln

| Regel | Detail |
|---|---|
| **Ort** | `docs/system/` — nummeriert `00_` … `11_` |
| **Sprache** | Deutsch (wie Ebene 2) |
| **Inhalt** | End-to-End-Flows, Enforcement-Matrizen, UI-Karten, Runbooks — **kein** Symbol-für-Symbol (dafür Spiegel) |
| **Pflicht am Ende** | Abschnitt **Betroffene Spiegel-Dateien** mit Links unter `docs/docs/` |
| **Planungsdocs** | Nicht duplizieren — verlinken auf `01–15`; bei Widerspruch `15_implementation_status.md` pflegen |
| **Neues Feature** | Querschnitt aktualisieren **und** betroffene Spiegel-Dateien |
