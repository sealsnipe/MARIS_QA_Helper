# `backend/app/static/vendor/purify.min.js`

**Quellpfad:** `backend/app/static/vendor/purify.min.js`

## Zweck

Minifizierte **Third-Party-Bibliothek [DOMPurify](https://github.com/cure53/DOMPurify)** (v3.4.7, Apache-2.0 / MPL-2.0): entfernt unsicheres HTML aus vom Markdown-Parser erzeugtem Markup, bevor es in Chat-Bubbles eingefügt wird.

## Ablauf (kurz)

1. Script-Tag lädt `/static/vendor/purify.min.js` (global `DOMPurify`).
2. `app.js` → `renderMarkdown`: nach `marked.parse` → `DOMPurify.sanitize(html, { USE_PROFILES: { html: true }, ADD_ATTR: ["target"] })`.
3. Sanitisiertes HTML landet in `.markdown-body` innerhalb `.bubble.assistant`.

## Konfiguration / Parameter

| Aspekt | Detail |
|---|---|
| Globales Symbol | `DOMPurify` |
| Profil | `USE_PROFILES.html: true` |
| Zusatz-Attribute | `target` (für Links) |
| Fallback | Fehlt DOMPurify → escaped Plain-Text |

## Siehe auch

- [`../app.md`](../app.md) — `renderMarkdown`
- [`marked.min.md`](./marked.min.md) — Markdown-Parse davor
