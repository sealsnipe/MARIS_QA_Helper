# 08 — UI/UX-Design

**Stand:** 2026-06-02 · **Status:** verbindlich für MVP

Server-gerenderte Seiten (Jinja2) + minimales Vanilla-JS. Kein Frontend-Framework, kein
Build-Step. Ruhiges, vertrauenswürdiges Business-Tool. **Neu:** Kundenauswahl im Header und
Datei-Upload neben der Text-Eingabe.

---

## 1. Design-Prinzipien
1. **Vertrauen durch Belege:** jede Antwort zeigt ihre Quellen.
2. **Kunde immer sichtbar:** der aktive Kunde steht jederzeit im Header.
3. **Zustände sind sichtbar:** leer, lädt, Upload läuft, Extraktion fehlgeschlagen, kein Treffer, Fehler.
4. **Eine Sache pro Seite:** Login / Arbeiten.
5. **Destruktives bestätigen:** Löschen mit `confirm()`.

## 2. Seitenkarte
```text
/login   (öffentlich)   → Anmeldung
/        (geschützt)    → Hauptseite:
                           Header: App | Kunde: <Auswahl> | Abmelden
                           links:  Wissensdatenbank (Tabs: Text | Datei) + Dokumentliste
                           rechts: Chat (Fragen + Antworten + Quellen)
```
Bei **genau einem** Kunden zeigt der Header nur den Namen (kein Dropdown); bei mehreren ein
Auswahl-Dropdown.

## 3. Wireframes

### 3.1 Login (`/login`)
```text
┌───────────────────────────────────────┐
│              SUP_QA_Helper              │
│          Support-Wissensassistent       │
│     ┌─────────────────────────────┐     │
│     │ E-Mail                       │     │
│     │ Passwort                     │     │
│     └─────────────────────────────┘     │
│     [ Anmelden ]                         │
│     ⚠ E-Mail oder Passwort falsch        │
└───────────────────────────────────────┘
```

### 3.2 Hauptseite (`/`)
```text
┌───────────────────────────────────────────────────────────────────────────┐
│ SUP_QA_Helper     Kunde: [ Acme GmbH ▼ ]     sven@example.com   [Abmelden] │
├──────────────────────────────┬────────────────────────────────────────────┤
│  WISSENSDATENBANK (Acme)     │  CHAT (Acme)                                │
│  ┌ [ Text ] [ Datei ] ─────┐ │  ┌ Verlauf ─────────────────────────────┐  │
│  │ Text-Tab:               │ │  │ Du: Wie eskalieren wir VPN-Probleme?  │  │
│  │  Titel: [__________]    │ │  │ Assistent: Zuerst FortiGate prüfen[1],│  │
│  │  Text:  [          ]    │ │  │ nach 15 Min eskalieren [2].           │  │
│  │  [ Einpflegen ]         │ │  │  Quellen:                             │  │
│  │ Datei-Tab:              │ │  │  [1] VPN Runbook · Abschnitt 0        │  │
│  │  ┌ Dropzone ──────────┐ │ │  │  [2] Eskalation · Abschnitt 1         │  │
│  │  │ Datei hierher ziehen│ │ │  └───────────────────────────────────────┘  │
│  │  │ .txt .md .pdf .docx │ │ │  ┌ Frage ───────────────────────────────┐  │
│  │  │ max 30 MB           │ │ │  │ [ Frage eingeben…          ] [Senden] │  │
│  │  └────────────────────┘ │ │  └───────────────────────────────────────┘  │
│  └─────────────────────────┘ │                                              │
│  ┌ Dokumente (3) ──────────┐ │                                              │
│  │ • VPN Runbook  [pdf] 3 🗑│ │                                              │
│  │ • Eskalation   [txt] 1 🗑│ │                                              │
│  │ • Onboarding   [man] 2 🗑│ │                                              │
│  └─────────────────────────┘ │                                              │
└──────────────────────────────┴────────────────────────────────────────────┘
```
Quelle/Typ als kleines Badge: `man` (Text), `pdf`, `txt`, `md`, `docx` (später `jira`).

## 4. Komponenten
| Komponente | Verhalten |
|---|---|
| **Header** | App-Name; **Kunden-Auswahl** (Dropdown bei >1, sonst Label); E-Mail; „Abmelden". |
| **Kunden-Dropdown** | Wechsel → `POST /api/session/customer` → Seite neu laden (KB+Chat gescoped). |
| **KB-Tabs** | „Text" (Titel+Textarea+Einpflegen) / „Datei" (Dropzone + Auswahl-Button). |
| **Dropzone** | Drag&Drop + Klick; zeigt erlaubte Typen + Limit; Upload → `POST /api/documents`. |
| **Dokumentliste** | Titel, Typ-Badge, Chunk-Anzahl, Löschen; nur aktiver Kunde. |
| **Chat-Verlauf** | Bubbles; Assistent-Bubble enthält Quellenblock. |
| **Frage-Eingabe** | Enter sendet, Shift+Enter = Umbruch. |

## 5. Zustände (verbindlich)
| Bereich | Zustand | UI |
|---|---|---|
| Kunde | keiner aktiv (mehrere erlaubt) | Hinweis „Bitte Kunde wählen", KB/Chat deaktiviert |
| Dokumentliste | leer | „Noch kein Wissen für diesen Kunden." |
| Text einpflegen | lädt/Fehler/Erfolg | Button „Wird indexiert…"; rote Inline-Meldung; Liste refresh |
| Upload | läuft | Fortschritt/„Wird hochgeladen & indexiert…", Button disabled |
| Upload | falscher Typ | „Nur .txt, .md, .pdf, .docx erlaubt." |
| Upload | zu groß | „Datei überschreitet 30 MB." |
| Upload | Extraktion fehlgeschlagen | „Text konnte nicht extrahiert werden (Dokument: fehlgeschlagen)." |
| Chat | lädt/Fehler/kein Treffer | „…"-Platzhalter; Fehler-Bubble; No-Context-Text ohne Quellen |
| Löschen | Bestätigung | `confirm()` vor DELETE |

## 6. Interaktionsflüsse
- **Kunde wählen/wechseln:** Dropdown → POST → Reload; Header zeigt neuen Kunden; KB+Chat leeren/neu laden.
- **Text einpflegen:** Tab „Text" → ausfüllen → Einpflegen → Liste refresh.
- **Datei hochladen:** Tab „Datei" → Datei wählen/ziehen → Upload-Zustand → bei Erfolg Liste refresh;
  bei Typ-/Größen-/Extraktionsfehler klare Meldung, Liste ggf. mit `failed`-Status.
- **Fragen:** Frage → Nutzer-Bubble + „…" → Antwort ersetzt Platzhalter, Quellenblock rendern.
- **Löschen / Abmelden:** wie gehabt.

## 7. Visueller Stil
Neutral-dunkles Theme, eine `app.css`, CSS-Variablen:
```css
:root{
  --bg:#0f1115; --surface:#181b22; --border:#2a2f3a;
  --text:#e6e8ee; --text-muted:#9aa3b2; --accent:#4c8bf5;
  --danger:#e5534b; --ok:#3fb950; --radius:10px; --gap:16px;
  --font:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
}
```
- Typo: System-Font; Body 15–16px; Quellen 13px gedämpft; Badges klein/uppercase.
- Buttons: primär `--accent`, destruktiv `--danger`, disabled gedimmt.
- Bubbles: Nutzer rechts (gedämpft), Assistent links (`--surface`).
- Aktiver Kunde im Header hervorgehoben (z. B. `--accent`-Rahmen am Dropdown).

## 8. Responsiveness & Barrierefreiheit
- Breakpoint ~900px: KB oben, Chat unten (gestapelt).
- `:focus-visible`-Outline; echte `<button>`; `<label>`-Verknüpfung; Kontrast ≥ WCAG AA.
- Zustände auch textlich, nicht nur farblich.

## 9. JS-Umfang (`app/static/app.js`)
- `fetch`-Wrapper für `/api/...` (inkl. Multipart-Upload via `FormData`).
- Tabs Text/Datei; Einpflegen; Upload (Dropzone, Fortschritt, Fehlertypen); Chat (senden, Bubbles,
  Quellen, Zustände); Kundenwechsel (POST + reload); Löschen (`confirm()`+DELETE).
- Keine Client-Persistenz; Chatverlauf rein im DOM (kein Reload-Restore — akzeptiert).

## 10. Nicht im MVP
Mehrseitiges Routing, Markdown-Rendering der Antworten, Quellen-Vorschau-Popover, Mehrfach-Datei-
Upload (eine Datei pro Upload genügt), Admin-UI für Kunden.
