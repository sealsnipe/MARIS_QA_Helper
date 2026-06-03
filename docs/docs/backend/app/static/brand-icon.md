# `backend/app/static/brand-icon.svg`

**Quellpfad:** `backend/app/static/brand-icon.svg`

## Zweck

Kompaktes **MARIS-App-Icon** (48×48 px, Kreis mit Verlauf und stilisiertem „M“). Für Favicon, kleine Markenplatzierungen oder eingebettete SVG-Referenzen.

## Ablauf (kurz)

- Statische Auslieferung unter `/static/brand-icon.svg`.
- Keine Skript-Anbindung; Größe über umgebendes HTML/CSS.

## Konfiguration / Parameter

| Aspekt | Wert |
|---|---|
| ViewBox | `0 0 48 48` |
| Gradient-IDs | `maris`, `shine` |
| Barrierefreiheit | `aria-label="MARIS"`, `role="img"` |

## Siehe auch

- [`brand-banner.md`](./brand-banner.md)
- [`brand-logo.md`](./brand-logo.md)
