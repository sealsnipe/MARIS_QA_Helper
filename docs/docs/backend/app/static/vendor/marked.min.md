# `backend/app/static/vendor/marked.min.js`

**Quellpfad:** `backend/app/static/vendor/marked.min.js`

## Zweck

Minifizierte **Third-Party-Bibliothek [marked](https://github.com/markedjs/marked)** (v15.0.12, MIT): parst Markdown zu HTML im Browser. Wird in `app.js` (`renderMarkdown`) für Assistant-Nachrichten im Chat genutzt.

## Ablauf (kurz)

1. In Layout/Chat-Template vor `app.js` per `<script src="/static/vendor/marked.min.js">` geladen.
2. `app.js` prüft `typeof marked !== "undefined"`, setzt GFM-Optionen und ruft `marked.parse(source)` auf.
3. Ausgabe wird anschließend durch DOMPurify gesäubert.

## Konfiguration / Parameter

| Aspekt | Detail |
|---|---|
| Globales Symbol | `marked` |
| Optionen in `app.js` | `gfm: true`, `breaks: true`, `headerIds: false`, `mangle: false` |
| Fallback | Ohne `marked`: Plain-Text via `escapeHtml` |

## Siehe auch

- [`../app.md`](../app.md) — `renderMarkdown`, `setBubbleContent`
- [`purify.min.md`](./purify.min.md) — HTML-Sanitisierung nach Parse
