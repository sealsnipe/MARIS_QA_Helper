# `backend/app/templates/base.html`

**Quellpfad:** `backend/app/templates/base.html`

## Zweck und logischer Aufbau

Minimales **Root-HTML-Gerüst** ohne Navigation und ohne Sidebar. Es liefert die gemeinsame `<head>`-Struktur (Charset, Viewport, Titel, Favicon, `app.css`) und einen einzigen `<main>`-Container für den `content`-Block.

Dieses Layout wird für **eigenständige Vollseiten** genutzt, die nicht in die Sidebar-Navigation von `layout.html` eingebettet sind: Login (`login.html`) und das ältere Monolith-UI (`index.html`). Seiten mit Sidebar erben stattdessen direkt `layout.html`, das ein erweitertes HTML-Gerüst inklusive Navigation mitbringt.

Lesereihenfolge: DOCTYPE und `<html lang="de">` → `<head>` mit Block `title` → `<body>` mit `<main class="app-shell">` und Block `content`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `/static/brand-icon.svg`, `/static/app.css`
- **Wird genutzt von:**
  - `backend/app/templates/login.html` — Anmeldeseite
  - `backend/app/templates/index.html` — Legacy-Kombi-UI (KB + Chat in einer Seite)
- **HTTP / UI / CLI:** Keine direkte Route; wird indirekt über abgeleitete Templates gerendert (`GET /login` → `login.html`)
- **Daten:** keine

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `title` | Jinja-Block | `<title>`-Inhalt; Default: „MARIS - Q/A Helper“ |
| `content` | Jinja-Block | Hauptinhalt innerhalb von `<main class="app-shell">` |

Keine weiteren Blöcke (`vendor_scripts`, `scripts`, `page_title` existieren hier nicht).

## Funktionen und Klassen

Keine — statisches HTML-Gerüst mit zwei Jinja-Blöcken.

## HTML / JS / CSS — zusätzliche Hinweise

- **Kein `APP_BOOT`:** Abgeleitete Templates müssen Boot-Daten und Skripte selbst im `content`-Block einbinden (siehe `index.html`)
- **Kein `app.js` im Basis-Layout:** Nur Stylesheet; JavaScript wird von Kind-Templates optional nachgeladen
- **Semantik:** `<main class="app-shell">` umschließt den gesamten sichtbaren Seiteninhalt
- **Barrierefreiheit:** `lang="de"` auf `<html>`, Viewport-Meta für responsive Darstellung
