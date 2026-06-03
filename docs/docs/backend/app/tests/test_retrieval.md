# `backend/app/tests/test_retrieval.py`

**Quellpfad:** `backend/app/tests/test_retrieval.py`

## Zweck und logischer Aufbau

Reine Unit-Tests für `filter_sources_by_answer_citations` in `app.retrieval`: Quellenliste nach expliziten Zitaten `[n]` in der Modellantwort filtern, oder bei fehlenden Zitaten nur den stärksten Treffer behalten.

Keine Datenbank, keine Embeddings, keine HTTP-Calls — nur künstliche `sources`-Dicts und Antwortstrings.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.retrieval`: `filter_sources_by_answer_citations`
- **Wird genutzt von:** pytest; Produktionscode: `backend/app/routes.py` (nach Chat-Antwort)
- **HTTP / UI:** indirekt über `/api/chat`-Quellenfilterung
- **Daten:** keine
- **Abgedecktes Modul:** `backend/app/retrieval.py` (Funktion ab Zeile `filter_sources_by_answer_citations`, Regex `_CITATION_PATTERN`)

## Konstanten, Typen und Modulebene

Keine Symbole auf Modulebene in der Testdatei.

## Funktionen und Klassen

### `test_filter_sources_keeps_only_cited_numbers()`

**Beschreibung:** Antwort mit `[2]` liefert genau die Quelle mit `n == 2`.

**Parameter / Rückgabe:** Keine.

**Ablauf / lokale Variablen:**
- `sources` — drei Dicts mit `n` 1–3, `title`, `chunk_index`, `score`
- `filtered` — Ergebnis von `filter_sources_by_answer_citations(sources, "Die Zeiten stehen in [2].")`
- Assertions: `len(filtered) == 1`, `filtered[0]["n"] == 2`, `title == "B"`

**Aufrufer / Aufgerufene:** `filter_sources_by_answer_citations` — Zitat-Pfad mit `cited_numbers` / `cited_set`.

---

### `test_filter_sources_without_citations_keeps_best_hit()`

**Beschreibung:** Ohne `[n]` in der Antwort bleibt nur die Quelle mit höchstem `score`.

**Ablauf / lokale Variablen:** Zwei Quellen (Scores 0.6 und 0.9); Antwort `"Antwort ohne Zitat."`; erwartet `title == "B"` (höchster Score).

**Aufrufer / Aufgerufene:** Fallback-Zweig: `return [max(sources, key=lambda item: item.get("score", 0))]`.

## (Optional) Tests

- **Fixtures:** keine; autouse KI-Mocks irrelevant.
- **Abgedecktes Modul:** `backend/app/retrieval.py`.

| Test | Intent |
|---|---|
| `test_filter_sources_keeps_only_cited_numbers` | Nur zitierte Quellennummern in der UI-Liste |
| `test_filter_sources_without_citations_keeps_best_hit` | Fallback: ein stärkster Treffer ohne Zitate |
