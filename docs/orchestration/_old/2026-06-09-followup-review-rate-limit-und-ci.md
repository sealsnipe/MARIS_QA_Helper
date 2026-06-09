# Follow-up-Review & Implementationsanweisungen — 2026-06-09 (Runde 2)

**Status:** ERLEDIGT (Aufgaben A–C umgesetzt, einzeln committed, Tests+Tenant grün nach jeder; Doku-Spiegel; Datei nach _old/ verschoben)
**Basis:** HEAD `0a661a1` auf `main`, Testlauf → **189 passed, 0 failed**
**Bezug:** Review der Umsetzung von `_old/2026-06-09-review-und-implementationsplan.md` (Commits `936ed9c`…`0a661a1`)
**Verbindliche Regeln:** `docs/PROJECT_STANDARDS.md`, `docs/DOCUMENTATION_RULES.md` (Doku-Spiegel!), `docs/13_coding_agent_brief.md`

---

## Teil 1 — Review-Ergebnis Runde 1

### Abgenommen (nicht mehr anfassen)

- **Aufgabe 1 (Bild-Tests):** Sehr gut. PIL-`verify()` für Standalone-Uploads, realistische Rausch-Fixtures, `_is_meaningful_image` jetzt auch für DOCX-embedded mit explizitem Filter-Test. Besser als geplant.
- **Aufgabe 2 (Integration-Token):** Exakt nach Plan inkl. aller drei Testfälle (DB-only → 200, Rotation → ENV-Token 401, Override-auf-leer → 503). `compare_digest` erhalten. Abgenommen.
- **Aufgabe 3 (pdfimages):** Chirurgisch sauber. Toter Code raus, Extraktionspfad für `vision_ocr.py` erhalten, `poppler-utils` korrekt im Dockerfile. Abgenommen.
- **Aufgabe 4 (Error-Ref):** Abgenommen.
- **Aufgabe 7 (VectorStore-Copy-Fix + Doku):** Fix statt Doku gewählt wie empfohlen. Abgenommen.

### Nachbesserungsbedarf

#### N1 — Login-Rate-Limit ist wirkungslos (MUSS)

`routes.py` (Login-Handler, ab ~Zeile 446): Der Limit-Check passiert erst **nach** `verify_password` und nur im Fehlerzweig. Konsequenzen:

1. **Brute-Force wird nicht gestoppt.** Ein Angreifer kann unbegrenzt weiterprobieren; sobald das Passwort stimmt, loggt er sich auch im „gesperrten" Zustand ein. Der eigene Test beweist das: Direkt nach dem 11. Versuch (`rate_limited`) geht `r_ok` mit korrektem Passwort durch — und der Test wertet das als gewünschtes Verhalten.
2. **Argon2 läuft weiterhin bei jedem Versuch** — auch der Ressourcenschutz fehlt.

Das Limit ändert aktuell nur die Redirect-URL der Fehlermeldung. Die Absicht von F5 (Brute-Force tatsächlich drosseln) ist nicht erfüllt.

#### N2 — CI-Job `docker-smoke` schlägt bei jedem Push fehl (MUSS)

`.github/workflows/test.yml`: `docker build -t maris-qa-helper-test ./backend` nutzt `./backend` als Build-Kontext. Das Dockerfile kopiert aber Repo-Root-relativ (`COPY backend/pyproject.toml .`, `COPY backend/app ./app`, `COPY scripts ./scripts`) — so baut es auch `docker-compose.yml` (`context: .`, `dockerfile: backend/Dockerfile`). Mit Kontext `./backend` existieren diese Pfade nicht → Build bricht ab. Der Job, der Dockerfile-Drift fangen soll, ist selbst der Drift.

#### N3 — Kleinere Punkte (SOLL, im selben Zyklus miterledigen)

- `_login_failures` wächst unbegrenzt: Fehlversuche mit immer neuen E-Mails legen immer neue Keys an; nur Erfolg poppt den eigenen Key. Speicher-Growth durch Random-E-Mail-Spam möglich.
- IP-Normalisierung `"test" in client_ip.lower()` ist ein fragiler Test-Hack im Produktionscode (jeder Hostname, der „test" enthält, kollabiert auf 127.0.0.1).
- `docs/07_auth_and_security.md` enthält den widersprüchlichen Satz „Rate-Limiting/Brute-Force-Schutz beim Login: nicht im MVP (intern akzeptiert). (F5 umgesetzt 2026-06-09.)".
- Neue Pillow-DeprecationWarning in `image_inspect.py:78` (`getdata` → entfällt in Pillow 14, Okt 2027). Nur Hinweis, **nicht** in diesem Zyklus fixen.

---

## Teil 2 — Implementationsanweisungen

Reihenfolge verbindlich, jede Aufgabe einzeln committen. Nach jeder Aufgabe: `cd backend && PYTHONPATH=. python3 -m pytest -q` muss 0 failed sein.

### Aufgabe A — Rate-Limit wirksam machen (N1 + N3-Teile)

In `backend/app/routes.py`, Login-Handler:

1. **Check vor die Passwortprüfung ziehen.** Ablauf neu:
   ```
   key bilden → fails laden + Fenster prunen
   if len(fails) >= _LOGIN_RATE_MAX_FAILS:
       → sofort Redirect /login?error=rate_limited (KEIN verify_password, KEIN DB-User-Lookup nötig)
   user laden + verify_password
   bei Fehlschlag: fails.append(now); speichern; Redirect error=1
   bei Erfolg: _login_failures.pop(key); Session setzen
   ```
   Damit gilt: Im Sperrfenster wird **auch das korrekte Passwort abgelehnt**, und Argon2 läuft für gesperrte Keys gar nicht erst.
2. **Semantik-Klarstellung:** `>=` statt `>` — nach 10 Fehlversuchen ist der 11. Versuch (egal ob richtig oder falsch) geblockt, bis das Fenster (60 s) abgelaufen ist.
3. **Pruning gegen Memory-Growth:** Beim Eintritt in den Handler, wenn `len(_login_failures) > 1000`: alle Keys entfernen, deren letzter Timestamp älter als `_LOGIN_RATE_WINDOW_S` ist. Eine Zeile Dict-Comprehension genügt; Schwellwert als Konstante `_LOGIN_RATE_PRUNE_THRESHOLD`.
4. **IP-Hack entschärfen:** Die `"test" in client_ip.lower()`-Logik entfernen. Stattdessen kleine Helper-Funktion `_login_rate_key(request, norm_email) -> tuple[str, str]`, die schlicht `request.client.host or "unknown"` nimmt. Im Docstring/Kommentar festhalten: hinter Reverse-Proxy ist das die Proxy-IP → Limit wirkt faktisch pro E-Mail; bewusst akzeptiert (kein X-Forwarded-For-Parsing im MVP, da Header spoofbar ohne Trusted-Proxy-Konfiguration). Falls der bestehende Test dadurch flaky wird (TestClient-IP variiert), im Test die IP per `client = TestClient(app, client=("1.2.3.4", 80))` o. ä. stabilisieren — **nicht** wieder im Produktionscode.
5. **Tests anpassen/ergänzen** in `test_auth.py`:
   - Bestehenden Test umbauen: Nach 10 Fehlversuchen muss der 11. Versuch **mit korrektem Passwort** ebenfalls `rate_limited` liefern (das ist der Kern der Nachbesserung).
   - Reset-Pfad: Fenster künstlich ablaufen lassen (Timestamps im `_login_failures`-Dict direkt um 61 s zurückdatieren — kein `sleep`), dann korrektes Passwort → Login klappt → danach ist der Key gepoppt.
   - Pruning: >1000 künstliche abgelaufene Keys einfüllen, ein Login-Request, Dict ist geschrumpft.
   - Wichtig: `_login_failures` in den betroffenen Tests vorher/nachher leeren (Fixture oder `clear()`), damit keine Testreihenfolge-Abhängigkeit entsteht.
6. Doku-Spiegel: `docs/docs/backend/app/routes.md`, `test_auth.md`.

**Akzeptanz:** Korrektes Passwort wird im Sperrfenster abgelehnt; kein `verify_password`-Aufruf für gesperrte Keys; Dict wächst nicht unbegrenzt; kein Test-Hack mehr im Produktionscode; Suite grün.

### Aufgabe B — CI docker-smoke fixen (N2)

In `.github/workflows/test.yml`, Job `docker-smoke`:

```yaml
- name: Docker build (backend image, repo-root context wie docker-compose)
  run: docker build -f backend/Dockerfile -t maris-qa-helper-test .
```

Kontext = Repo-Root (`.`), identisch zu `docker-compose.yml`. Doku-Spiegel `docs/docs/.github/workflows/test.md` nachziehen.

**Akzeptanz:** `docker build -f backend/Dockerfile .` läuft lokal durch (wenn Docker auf der Maschine verfügbar ist; sonst genügt die Pfad-Verifikation: alle `COPY`-Quellen existieren relativ zur Repo-Root).

### Aufgabe C — Doku-Widerspruch auflösen (N3)

`docs/07_auth_and_security.md`: Den Satz zum Rate-Limiting ersetzen durch eine konsistente Aussage, z. B.:
„**Rate-Limiting beim Login:** In-Memory-Sliding-Window (10 Fehlversuche / 60 s pro IP+E-Mail), blockt im Sperrfenster auch korrekte Passwörter, Reset nach Fensterablauf oder Erfolg. Ausreichend bei `--workers=1`; hinter Reverse-Proxy wirkt das Limit faktisch pro E-Mail (Proxy-IP). Umgesetzt 2026-06-09 (F5), nachgeschärft Runde 2."

### Explizit NICHT in diesem Zyklus

- Kein X-Forwarded-For-Parsing / Trusted-Proxy-Konfiguration.
- Kein persistentes Rate-Limit (Redis o. ä.) — In-Memory bei `--workers=1` bleibt die dokumentierte Annahme.
- Pillow-`getdata`-Deprecation nicht anfassen (separater Task, Zeitdruck erst 2027).
- Keine weiteren Refactorings.

---

## Abschluss-Checkliste für den Coder

- [x] Aufgaben A–C einzeln committed, Commit-Messages nach bisherigem Stil
- [x] `cd backend && PYTHONPATH=. python3 -m pytest -q` → 0 failed
- [x] `pytest app/tests/test_tenant_isolation.py -q` explizit grün
- [x] Neuer Test beweist: korrektes Passwort im Sperrfenster → `rate_limited`
- [x] Doku-Spiegel gemäß `DOCUMENTATION_RULES.md` für jede geänderte Datei aktualisiert
- [x] Diese Datei nach `docs/orchestration/_old/` verschieben und Status oben auf ERLEDIGT setzen
