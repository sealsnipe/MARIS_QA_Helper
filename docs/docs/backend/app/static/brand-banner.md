# `backend/app/static/brand-banner.svg`

**Quellpfad:** `backend/app/static/brand-banner.svg`

## Zweck

Horizontales **MARIS-Markenbanner** (240×58 px) für Sidebar und Login: Verlaufshintergrund (Blau–Grün), dekoratives Gitter, EKG-ähnliche Linie und stilisiertes „M“-Icon. `aria-label="MARIS"`, `role="img"`.

## Ablauf (kurz)

- Wird statisch aus `/static/brand-banner.svg` eingebunden (z. B. `<img class="sidebar-banner">`, Login-Banner).
- Keine Laufzeitlogik; Skalierung über CSS (`object-fit: cover`, feste Höhe 58 px).

## Konfiguration / Parameter

| Aspekt | Wert |
|---|---|
| ViewBox | `0 0 240 58` |
| Farben | MARIS-Palette `#004A85` … `#96C45A`, Akzent `#B8E06A` |
| Einbindung | `backend/app/templates/layout.html`, Login-Template |

## Siehe auch

- [`brand-icon.md`](./brand-icon.md) — rundes Icon
- [`brand-logo.md`](./brand-logo.md) — Logo mit Text „Q/A HELPER“
- [`app.css.md`](./app.css.md) — `.sidebar-banner`, `.login-brand-banner`
