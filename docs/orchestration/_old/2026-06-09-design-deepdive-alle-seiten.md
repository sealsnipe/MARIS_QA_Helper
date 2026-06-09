# Design-Deep-Dive: alle Seiten — Review & Implementationsplan — 2026-06-09 (Runde 3)

**Status:** ERLEDIGT (Aufgaben A–F umgesetzt, einzeln committed, Tests+Tenant grün, Mirrors, Smoke; Datei nach _old/ verschoben)
**Basis:** HEAD `0a661a1`, Review-Methode: vollständige statische Analyse aller 17 Templates + `app.css` (3561 Z.) + `app.js` (4614 Z.) gegen `docs/08_ui_ux_design.md` und `PROJECT_STANDARDS.md`
**Hinweis:** Voraussetzung ist, dass Runde 2 (`2026-06-09-followup-review-rate-limit-und-ci.md`) abgeschlossen ist oder unabhängig committet wird — keine Datei-Überschneidung außer `routes.py` (hier nur Route-Löschung, dort Login-Handler).
**Verbindliche Regeln:** `docs/PROJECT_STANDARDS.md` (Gate A — **kein** Refactor von app.js/routes.py), `docs/DOCUMENTATION_RULES.md` (Doku-Spiegel!)

---

## Teil 1 — Querschnitts-Review (betrifft alle Seiten)

### Q1 — Undefinierte CSS-Variablen (BUG, visuell)

`app.css` nutzt `var(--muted)` an 6 Stellen und `var(--panel)` an 1 Stelle (z. B. `.info-tip`, Z. 1789, 1823) — **beide sind in `:root` nie definiert** (definiert sind `--text-muted` und `--panel-bg`). Folge: Die Deklarationen sind „invalid at computed-value time" und fallen auf Initial-/Erbwerte zurück — der Info-Tip-Rahmen ist z. B. nur durch Zufall (currentColor) sichtbar. Fix: alle `var(--muted)` → `var(--text-muted)`, `var(--panel, …)` → `var(--panel-bg)`.

### Q2 — Tote Templates & Legacy-Seite

- **`index.html` (92 Z.) ist toter Code:** altes Zwei-Spalten-Layout mit eigenem, inkompatiblem `APP_BOOT` und altem Branding „SUP_QA_Helper". Wird von **keiner Route** gerendert (grep-verifiziert). Löschen.
- **`admin_keys.html`** ist nur noch über `/admin/keys/legacy` erreichbar (nicht in der Nav); `/admin/keys` leitet auf `/admin/keys/assignments` um. Die Legacy-Seite enthält ein eigenes OAuth-Dialog-Markup mit denselben Element-IDs (`oauth-verify-url`, `oauth-user-code`) wie die Presets-Seite. Kein Test hängt an `/admin/keys/legacy` (grep-verifiziert; `test_admin_keys.py` testet Redirect + presets/assignments + API). Löschen: Template, Route, `initKeysPage()` in app.js (Z. 2937–3203) und der Dispatch `page === "admin_keys"`.

### Q3 — Modals ohne einheitliches Verhalten (A11y/UX)

Drei Modal-Familien, drei Verhaltensweisen:

| Modal | Escape | Backdrop-Klick | Fokus-Management |
|---|---|---|---|
| Lightbox (Bild-Vollansicht) | ✅ | ? | ❌ |
| KC-Detail-Modal | ✅ | ✅ | ❌ |
| Keys: Preset-Form + OAuth-Wizard | ❌ | ❌ | ❌ |
| Vision-OCR-Bildauswahl | ❌ | ❌ | ❌ |

Kein Modal setzt beim Öffnen den Fokus in den Dialog oder stellt ihn beim Schließen wieder her; `aria-modal="true"` ist gesetzt, aber Tab läuft ungehindert in den Hintergrund. Für ein internes Tool kein Blocker, aber leicht vereinheitlichbar (siehe Aufgabe C).

### Q4 — Branding/Wording-Inkonsistenzen

- App-Name in drei Varianten: „MARIS - Q/A Helper" (Titles), „MARIS Q/A Helper" (Brand-Text), „SUP_QA_Helper" (FastAPI `title` in `main.py`, totes `index.html`).
- Login-`<title>` trennt mit „—", alle anderen Seiten mit „·".
- Login-Seite hat **kein `<h1>`** (Brand-Titel ist ein `<p class="login-brand-title">`).
- `ICON_SAVE` (app.js Z. 2167) trägt hartkodiertes Inline-Grün `#2e7d32` statt `var(--ok)`; `tools/bild_zu_text.html` hat ein Inline-`style="margin-top…"`-Attribut — beides gegen die eigene Token-Disziplin.

### Q5 — Clipboard-Buttons scheitern still unter HTTP (UX-Falle)

Alle „Kopieren"-Buttons (Bild-zu-Text: Text/Mermaid; OAuth-Wizard: Code) nutzen `navigator.clipboard.writeText` mit leerem `catch {}`. In **Non-Secure-Contexts** (HTTP im LAN, z. B. `http://server:8088` — laut DEPLOY-Doku ein realer Betriebsmodus vor TLS) ist `navigator.clipboard` `undefined` → Klick tut **nichts, ohne jede Rückmeldung**. Fix: Fallback (`document.execCommand("copy")` über temporäre Textarea) und bei endgültigem Scheitern eine Statusmeldung.

### Q6 — Info-Tips: gut gelöst, ein Rest

Positiv (Korrektur zur Annahme im Code): app.js setzt global `tabindex="0"` auf alle `.info-tip`, CSS zeigt Tooltip bei `:hover` **und** `:focus` — Keyboard funktioniert. Rest-Finding: Screenreader hören nur „i". Fix: `role="note"` weglassen, stattdessen `aria-label` mit dem Tooltip-Text setzen (im selben globalen Handler: `tip.setAttribute("aria-label", tip.dataset.tip)`).

### Q7 — Mobile (~<900px): bewusste Schwäche, dokumentieren

Die Sidebar stapelt sich vollständig **über** den Inhalt (kein Collapse/Hamburger) — auf schmalen Screens schieben Kundenwahl + Chatliste + Nav den Inhalt weit nach unten. Chat hat eine Sonderbehandlung (`100dvh`-Grid), die übrigen Seiten nicht. **Entscheidung: kein Umbau in diesem Zyklus** (internes Desktop-Tool), aber in `docs/08` §8 als bekannte Einschränkung festhalten.

### Q8 — `docs/08_ui_ux_design.md` driftet stark vom Ist

- §3.2-Wireframe zeigt das **alte Header-Layout** (Kunde im Header) statt Sidebar.
- §2-Seitenkarte fehlen: Tools (Bild zu Text), Knowledge Center (3 Seiten), Keys-Subpages (presets/assignments), `/admin/keys/legacy`.
- §7 nennt nicht `--panel-bg` und `color-scheme: dark`.
- §10 „Nicht im MVP" behauptet „kein Markdown-Rendering" — Chat rendert längst Markdown via `marked` + `DOMPurify` (sicher umgesetzt, gut!), und „Mehrfach-Datei-Upload" gibt es im Bild-zu-Text-Tool.

### Was querschnittlich gut ist (nicht anfassen)

- **XSS-Disziplin:** durchgehend `escapeHtml`/`escapeAttr` bei allen `innerHTML`-Renderings (stichprobenartig über alle Seiten verifiziert); Chat-Markdown über DOMPurify mit HTML-Profil; Mermaid mit `securityLevel: "strict"`.
- **Status-Pattern:** jede Seite hat `aria-live="polite"`-Statuselemente, konsistente „lädt/ok/error"-Meldungen mit Fehlercode-Mapping auf deutsche Texte.
- **Destruktives bestätigen:** alle 8 Löschpfade haben `confirm()`.
- **Fokus-Sichtbarkeit:** zentrale `:focus-visible`-Regeln für button/input/textarea/select/dropzone.
- Tenant-Banner („Bitte Kunde wählen") + `customer_nav_mode`-Logik (scoped/admin_scoped/global) funktioniert konsistent über `APP_BOOT`.

---

## Teil 2 — Seiten-Deep-Dives

### 1. `/login`

**Gut:** `role="alert"` für Fehler, korrekte `autocomplete`-Attribute, Label-Verknüpfung, differenzierte Rate-Limit-Meldung.
**Findings:** kein `<h1>` (Q4); Title-Trenner „—" (Q4).

### 2. `/chat`

**Gut:** Enter sendet / Shift+Enter Umbruch, Submit-Lock während Request, Lade-Bubble, Quellen nur bei Kontext, Markdown sicher gerendert, Chat-Historie in Sidebar mit Lösch-confirm, URL-Param `?c=` für Deep-Link auf Chats.
**Findings:**
- **Kein Empty-State:** Beim ersten Besuch ist der Chatbereich eine leere dunkle Fläche — `docs/08` §1.3 verlangt sichtbare Zustände. Empfehlung: zentrierter Hinweis („Stelle eine Frage zur Wissensbasis von {Kunde}. Antworten enthalten Quellenangaben.") solange `chat-log` leer ist.
- Fehler-Bubble ist generisch („Antwort konnte nicht geladen werden") und verwirft `err.code`/`ref` — mindestens den Code in den `chat-status` schreiben (Muster der anderen Seiten).
- Textarea wächst nicht mit (fix `rows="2"`); Markdown-Mehrzeiler erfordern Scrollen im Mini-Feld. Nice-to-have: auto-resize bis ~6 Zeilen.

### 3. `/kb` (Wissensbasis, User)

**Gut:** Read-only-Banner für Global-Scope, Volltext-Dokumentsuche, kompakte Liste mit Badges (Typ, partial, Vision-OCR), Dropzone mit Maus/Tastatur (Enter/Space) + Strg+V, Duplikat-Dialog vor dem Anlegen.
**Findings:**
- Dropzone-Hint nennt „.png · .jpg · max. 30 MB", `accept` erlaubt zusätzlich `.webp/.gif` — Hint unvollständig.
- Empty-State-Text „Noch kein Wissen für diesen Kunden." erscheint laut Markup auch, wenn nur der **Suchfilter** nichts findet — dann wäre „Keine Treffer für ‚…'" richtig (verifizieren, ggf. unterscheiden).

### 4. `/admin/knowledge` (Wissensdatenbanken, Admin)

**Gut:** identisches, bewährtes KB-Pattern; Scope folgt der Sidebar (admin_scoped) inkl. Global.
**Findings:**
- **Kein sichtbarer Scope im Hauptbereich:** Welche KB man gerade bearbeitet (Global vs. Kunde X) steht nur in der Sidebar. Bei einer destruktiven Admin-Seite gehört ein Scope-Badge in den Seitenkopf („Bearbeite: **Global**" / „Bearbeite: **BG Frankfurt**").
- Dropzone-Hint hat hier **kein** Größenlimit (KB-Seite nennt 30 MB) — vereinheitlichen (Aufgabe E).

### 5. `/admin/prompts` (Systemprompts)

**Gut:** schlicht, Info-Tip erklärt Global-vs-Kunde-Semantik.
**Findings (gravierendste UX-Lücke des Reviews):**
- **Scope unsichtbar + Datenverlust:** Die Seite zeigt nirgends, ob gerade der globale oder ein Kunden-Prompt im Editor steht. Wechselt man den Sidebar-Kunden, wird die Textarea **kommentarlos mit dem anderen Prompt überschrieben** — ungespeicherte Änderungen sind weg. Es gibt keinen Dirty-Indikator und keinen Guard.
- Empfehlung: Scope-Badge wie bei 4. + Dirty-Tracking (Vergleich gegen geladenen Stand): bei Scope-Wechsel mit ungespeicherten Änderungen `confirm()`, zusätzlich `beforeunload`-Guard.

### 6. `/admin/customers` (Kundenverwaltung)

**Gut:** Inline-Edit für Slug+Name, explizites Migrations-Feedback („… migriere KB (Qdrant) …" → Erfolgsmeldung), Slug-Validierung client- und serverseitig, sehr gutes Fehlercode-Mapping (customer_exists, vector_store_failed, …), Fehlerfall lässt Edit-Mode offen.
**Findings:**
- **Kein Button-Lock während der Migration:** `customer-save-btn` wird beim Speichern nicht disabled — bei einer langlaufenden Qdrant-Migration kann ein zweiter Klick eine **zweite parallele PATCH** auslösen. Save/Cancel/Delete der Zeile während des Requests sperren (dasselbe Muster wie der „Einpflegen"-Lock aus Commit `8ace6cf`).
- **Delete-Confirm verschweigt die Tragweite:** „Kunde ‚X' wirklich entfernen?" — es fehlt, dass KB (Qdrant-Collection), Uploads und Chat-Verläufe betroffen sind. Confirm-Text präzisieren.
- „Abbrechen" ist ein Text-Button mit Klasse `icon-btn` zwischen echten Icon-Buttons — als Icon (×) oder als normaler `secondary small` ausführen.

### 7. `/admin/users` (Benutzer)

**Gut:** Rollen-Preset-Anwendung live beim Anhaken (setzt Admin + Kunden), Edit-Row-Pattern, Selbstschutz-Fehlercodes (cannot_demote_self / cannot_deactivate_self) sauber gemappt.
**Finding:** **Terminologie-Mismatch beim „Löschen":** Trash-Icon + `aria-label="Entfernen"` + Status „Entfernen…", aber die Aktion **deaktiviert** nur (confirm sagt korrekt „deaktivieren", Erfolgsmeldung „Benutzer deaktiviert"). Einheitlich „Deaktivieren": anderes Icon (z. B. Person-Off/Ban) oder mindestens aria-label/Status angleichen.

### 8. `/admin/roles` (Rollen)

**Gut:** Toggle-Buttons mit `aria-pressed`, „Auto-Kunden"-Toggle hakt alle Kunden an, Edit-Row wie Users.
**Finding:** Toggle-Beschriftungen **„ADM"/„AK" sind kryptisch** — Bedeutung nur im `title`-Tooltip. Ausschreiben („Admin", „Auto-Kunden") — Platz ist vorhanden — oder Label daneben.

### 9. `/admin/keys/presets` (LLM Presets)

**Gut:** Karten-Grid, Provider-Katalog mit „(demnächst)"-Disabled-Optionen, OAuth-Wizard mit Schrittanzeige, Poll-Logik robust (invalid_grant-Selbstheilung, In-Flight-Lock), Code-kopieren-Button.
**Findings:** Modals ohne Escape/Backdrop/Fokus (Q3); Copy-Button mit Silent-Fail (Q5).

### 10. `/admin/keys/assignments` (LLM Zuordnung)

**Gut:** klare Subnav Presets/Zuordnung, Slots-Tabelle + „Weitere Keys" getrennt.
**Findings:** keine seitenspezifischen über die Querschnittsthemen hinaus.

### 11. `/admin/keys/legacy`

Löschen (Q2).

### 12. `/tools/knowledge-center` (Content Dashboard)

**Gut:** Karten als echte `<button>` (voll tastaturbedienbar — bestes A11y-Pattern der App), Status-/Quellen-Filter + entprellte Suche, „Mehr laden"-Paginierung, Detail-Modal mit Escape + Backdrop + Tabs (Überarbeitet/Original/Änderungen) und Adopt-Ziel-Hinweis auf Sidebar-Kunden.
**Findings:** `window.__kcDetailView`/`__kcActiveRevisionChanges` als globale Variablen — funktional, aber fragil (kein Umbau in diesem Zyklus, nur als Hinweis festgehalten).

### 13. `/tools/knowledge-center/submit` (Content vorschlagen)

**Gut:** Scope-Hinweis auf aktiven Mandanten direkt auf der Seite (genau das, was 4./5. fehlt!), KI-Toggle mit erklärtem Aus/An-Verhalten, Pipeline-Builder mit Reihenfolge-Chips (↑/↓/× mit aria-labels, max 4 mit disabled-State), localStorage-Persistenz der Auswahl, „Meine Vorschläge"-Liste.
**Findings:** keine nennenswerten — die Seite ist das Vorbild für Scope-Sichtbarkeit.

### 14. `/tools/knowledge-center/sources`

**Gut:** Standard-Pattern (Create-Form + Tabelle), `pattern`-Validierung für Host-Code, Unveränderlichkeit im Info-Tip erklärt.
**Finding:** Delete-Confirm „Quelle wirklich löschen?" nennt als einziger Confirm-Dialog **nicht den Namen** des Objekts — angleichen.

### 15. `/tools/bild-zu-text`

**Gut:** sauberste Zustandsführung der App (Dropzone leer/gefüllt, Transcribe-Button-Lock, Pro-Bild-Fehlerkarten), Objekt-URLs werden korrekt revoked, Mermaid mit Diagramm/Code-Toggle und striktem Security-Level, Ergebnis-Textareas readonly mit dynamischer Höhe.
**Findings:** Copy-Silent-Fail (Q5); alte Ergebnisse bleiben unter Umständen stehen, wenn man danach Bilder ändert und erneut transkribiert — verifizieren, dass `renderResults` die Liste vollständig ersetzt (tut es) und beim „Alle entfernen" auch die Ergebnisse geleert werden (prüfen, sonst leeren).

---

## Teil 3 — Implementationsplan

Reihenfolge verbindlich, jede Aufgabe einzeln committen. Nach jeder Aufgabe: `cd backend && PYTHONPATH=. python3 -m pytest -q` → 0 failed (Frontend-Änderungen können Template-/Routen-Tests berühren!). Da es keine JS-Tests gibt, gilt für jede Aufgabe zusätzlich: **manuelle Smoke-Prüfung der betroffenen Seite(n)** über `dev_local.sh` (Port 8090) und Browser; in der Commit-Message kurz vermerken, was geprüft wurde.

### Aufgabe A — Tote Templates & Legacy entfernen (Q2)

1. `backend/app/templates/index.html` löschen.
2. `backend/app/templates/admin_keys.html` löschen; Route `/admin/keys/legacy` aus `routes.py` entfernen (der Redirect `/admin/keys` → assignments **bleibt**); `initKeysPage()` (app.js Z. 2937–3203) + Dispatch-Zeile `if (page === "admin_keys") initKeysPage();` entfernen; `admin_keys`-Eintrag aus den `admin_nav_pages`-Listen in `layout.html` entfernen.
3. Grep-Verifikation: keine Referenz mehr auf `admin_keys.html`, `index.html`, `initKeysPage`, `keys/legacy` (außer Doku-Archiv).
4. Doku-Spiegel: betroffene Mirror-Dateien unter `docs/docs/` löschen/anpassen, `docs/docs/INDEX.md` aktualisieren.

**Akzeptanz:** Suite grün (insb. `test_admin_keys.py`); `/admin/keys` redirectet weiterhin; `/admin/keys/legacy` → 404.

### Aufgabe B — CSS-Token- und Stil-Hygiene (Q1, Q4-Teile)

1. `app.css`: alle `var(--muted` → `var(--text-muted`, `var(--panel,`/`var(--panel)` → `var(--panel-bg` (7 Stellen, grep `var(--muted\|var(--panel[,)]`).
2. `ICON_SAVE` in app.js: Inline-`style="color:#2e7d32"` entfernen, stattdessen CSS-Regel `.icon-btn.save .icon-btn-svg { color: var(--ok); }`.
3. `tools/bild_zu_text.html`: Inline-`style`-Attribut in eine Klasse (`.bild-tool-subheader` o. ä.) überführen.
4. `main.py`: FastAPI `title="MARIS Q/A Helper"`; `login.html`-Title-Trenner auf „·"; Login-Brand-`<p>` → `<h1 class="login-brand-title">` (CSS prüfen, Stil beibehalten).

**Akzeptanz:** grep findet keine undefinierten `var(--…)`-Namen mehr (Abgleich gegen `:root`-Liste); Login zeigt unverändertes Layout mit `<h1>`.

### Aufgabe C — Modal-Verhalten vereinheitlichen (Q3)

1. Kleine Helper-Funktion in app.js (bei den anderen Shared-Helpers, ~Z. 100): `bindModalBasics(modal, { onClose })` → registriert Escape (nur wenn Modal sichtbar), Backdrop-Klick (`event.target === modal`), merkt sich `document.activeElement` beim Öffnen und stellt ihn beim Schließen wieder her, setzt beim Öffnen Fokus auf das erste fokussierbare Element im Dialog. **Kein vollständiger Fokus-Trap nötig** (Scope-Entscheidung — internes Tool).
2. Anwenden auf: Preset-Form-Modal, OAuth-Wizard (Achtung: Schließen muss weiterhin `closeOAuthModal()` mit Poll-Stop aufrufen), Vision-OCR-Bildauswahl-Modal, Lightbox. KC-Detail-Modal auf den Helper umstellen (Verhalten identisch, Code dedupliziert).
3. Manuell prüfen: OAuth-Wizard per Escape schließen stoppt den Poll (Netzwerk-Tab: keine weiteren `/oauth/poll`-Requests).

**Akzeptanz:** Alle 5 Modals: Escape + Backdrop schließen, Fokus landet im Dialog und kehrt zum Auslöser zurück.

### Aufgabe D — Scope-Sichtbarkeit + Dirty-Guard für Admin-Seiten (Findings 4, 5)

1. Wiederverwendbares Scope-Badge: in `admin_knowledge.html` und `admin_prompts.html` oben im Panel `<p class="admin-scope-indicator">Bearbeite: <strong id="admin-scope-label"></strong></p>`; app.js setzt den Text in `initAdminKnowledgePage`/`initAdminPromptsPage` und bei Sidebar-Wechsel (admin_scoped-Pfad) auf „Global" bzw. Kundennamen. Vorbild-Wording: KC-Submit-Seite.
2. Dirty-Guard Prompts: geladenen Stand merken; bei Sidebar-Scope-Wechsel mit `textarea.value !== loaded` → `confirm("Ungespeicherte Änderungen am Prompt verwerfen?")`, bei Abbruch Select auf alten Wert zurücksetzen und nicht neu laden; zusätzlich `beforeunload`-Handler solange dirty.
3. Nach Speichern/Laden Dirty-Zustand zurücksetzen.

**Akzeptanz:** Scope jederzeit im Hauptbereich sichtbar; Prompt-Wechsel mit ungespeicherten Änderungen fragt nach; Speichern entschärft den Guard.

### Aufgabe E — Gesammelte Klein-Fixes (Findings 2, 3, 6, 7, 8, 14, Q5, Q6)

Ein Commit, jede Änderung wenige Zeilen:

1. **Chat-Empty-State:** Platzhalter-Div im `chat-log`, sichtbar solange keine Bubbles (bei `renderChatLog`/`appendBubble` ausblenden). Text siehe Teil 2.2.
2. **Chat-Fehlerdetail:** im catch `err.code`/`err.ref` an `chat-status` anhängen („Chat fehlgeschlagen (internal_error, ref a1b2c3)." falls vorhanden).
3. **Dropzone-Hints vereinheitlichen** (kb.html, admin_knowledge.html): „.txt · .md · .pdf · .docx · Bilder (.png .jpg .webp .gif) · max. 30 MB".
4. **Customers:** Save/Cancel/Delete-Buttons der Zeile während PATCH/DELETE disablen; Delete-Confirm: „Kunde ‚X' wirklich entfernen? KB-Dokumente, Uploads und Chat-Verläufe dieses Kunden werden mit entfernt." (Wortlaut ggf. an tatsächliches Backend-Verhalten anpassen — vorher in `customers.py` verifizieren, was DELETE kaskadiert!); „Abbrechen"-Button als `secondary small` ohne `icon-btn`.
5. **Users:** Deaktivieren-Terminologie konsistent (aria-label „Deaktivieren", Status „Deaktivieren…"); Icon optional behalten.
6. **Roles:** Toggle-Beschriftung „Admin" und „Auto-Kunden" ausschreiben (CSS-Breite prüfen).
7. **KC Sources:** Delete-Confirm mit Quellnamen.
8. **Clipboard-Helper** `copyToClipboard(text, btn, statusEl?)`: erst `navigator.clipboard`, Fallback temporäre Textarea + `execCommand("copy")`, bei Misserfolg Statusmeldung „Kopieren nicht möglich — Text manuell markieren."; alle 3+ Copy-Stellen umstellen.
9. **Info-Tips:** im globalen Handler zusätzlich `tip.setAttribute("aria-label", tip.dataset.tip || "Information")`.
10. **Bild zu Text:** „Alle entfernen" leert auch `transcribe-results`.
11. **KB-Empty vs. Suchtreffer:** wenn Suchfeld gefüllt und 0 Treffer → „Keine Treffer für ‚…'." statt „Noch kein Wissen…" (gilt für kb + admin_knowledge; im gemeinsamen Render-Pfad lösen).

### Aufgabe F — `docs/08_ui_ux_design.md` auf Ist-Stand bringen (Q7, Q8)

1. §2 Seitenkarte: Tools-/KC-/Keys-Subseiten ergänzen, `/admin/keys/legacy` streichen (nach Aufgabe A).
2. §3.2 Wireframe durch Sidebar-Layout-Wireframe ersetzen (Sidebar: Kunde/Chats/Tools/Einstellungen; Hauptbereich mit Seitentitel).
3. §7 Tokens komplettieren (`--panel-bg`, `color-scheme: dark`).
4. §8: Mobile-Einschränkung dokumentieren („Sidebar stapelt, kein Collapse — Desktop-first, bewusst").
5. §10: Markdown-Rendering und Mehrfach-Upload (Bild zu Text) aus „Nicht im MVP" entfernen; neue bewusste Auslassungen eintragen (Fokus-Trap, Mobile-Nav, Theme-Switcher).
6. Querverweis auf die in C/D eingeführten Patterns (Modal-Helper, Scope-Badge, Dirty-Guard).

### Explizit NICHT in diesem Zyklus

- Kein Split/Refactor von `app.js` oder `app.css` (Gate A) — alle Fixes sind chirurgisch.
- Kein Mobile-Hamburger / Sidebar-Collapse (nur Doku, Aufgabe F).
- Kein vollständiger Fokus-Trap, kein Frontend-Framework, kein Theme-Switcher, kein Auto-Resize der Chat-Textarea (nice-to-have, separat).
- Keine Änderung an den `window.__kc*`-Globals (funktional; nur Hinweis in Teil 2.12).

---

## Abschluss-Checkliste für den Coder

- [x] Aufgaben A–F einzeln committed, Commit-Messages nach bisherigem Stil, je mit Vermerk der manuell geprüften Seiten
- [x] `cd backend && PYTHONPATH=. python3 -m pytest -q` → 0 failed; `pytest app/tests/test_tenant_isolation.py -q` grün
- [x] grep-Verifikationen aus A und B dokumentiert ausgeführt
- [x] Manuelle Smoke-Prüfung: Login, Chat (leer + Frage), KB-Upload-Hint, beide Admin-KB/Prompts-Scope-Badges, Kunden-Edit-Lock, ein Modal pro Familie (Escape/Backdrop/Fokus), Copy-Button unter `http://` (Non-Secure-Context!)
- [x] Doku-Spiegel gemäß `DOCUMENTATION_RULES.md` für jede geänderte Datei; `docs/08` aktualisiert (Aufgabe F)
- [x] Diese Datei nach `docs/orchestration/_old/` verschieben, Status auf ERLEDIGT
