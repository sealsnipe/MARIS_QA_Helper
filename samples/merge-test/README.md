# Merge- & Duplikat-Testdaten

Fünf Texte zum manuellen Testen von Stufe 2 (Similarity) und Stufe 3 (Merge).

## Ablauf

1. **01**, **02**, **03** nacheinander in die Wissensdatenbank einpflegen (jeweils eigener Titel).
2. **04** hochladen → Inspect sollte Ähnlichkeit zu **01** und/oder **03** zeigen; Merge-Vorschau mischt übernommene Absätze mit neuem Inhalt.
3. **05** hochladen → Inspect sollte **stark ähnlich zu 01** melden („Rufbereitschaft“); **Einarbeiten in 01** testen.

## Erwartung (Richtwerte)

| Datei | Erwartung |
|-------|-----------|
| 01–03 | Keine Duplikate untereinander (verschiedene Themen) |
| 04 | `similar[]` mit 01 und/oder 03; Block-Diff: übernommen + neu |
| 05 | `similar[0]` ≈ **01** (hoher Score); Merge-Ziel = Eintrag 01 |

Alle Texte sind bewusst > 20 Zeichen und in Absätzen strukturiert (Merge-Blöcke).
