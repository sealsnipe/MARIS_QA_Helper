# 07 — Auth & Security

**Stand:** 2026-06-02 · **Status:** verbindlich für MVP

---

## 1. Ziel & Abgrenzung

Login-Schranke + **Mandanten-Zugriffskontrolle**: Nutzer melden sich an, sehen nur ihre
zugeordneten Kunden, und jede Operation ist serverseitig auf den aktiven Kunden geprüft. Kein
SSO, keine Rollen, kein Self-Signup im MVP. Passwörter werden **gehasht** (Einweg), nicht
verschlüsselt.

## 2. Passwort-Hashing
- **Argon2id** via `argon2-cffi` (`PasswordHasher`); Bibliotheks-Defaults genügen.
- Bewusst **kein** SHA-256/MD5. Salt + Parameter stecken im Hash-String (`users.password_hash`).
```python
from argon2 import PasswordHasher
ph = PasswordHasher()
password_hash = ph.hash(plaintext)     # beim Seed
ph.verify(password_hash, plaintext)    # beim Login (wirft bei Mismatch)
```

## 3. Sessions
- Starlette `SessionMiddleware` → signiertes `httponly`-Cookie. Keine Session-Tabelle.
- Inhalt: `session["user_id"]` und `session["customer_id"]` (aktiver Kunde). Sonst nichts Sensibles.
- `SESSION_SECRET` aus `.env` (Fail-fast bei Fehlen). Flags: `httponly`, `samesite="lax"`,
  `secure=true` sobald HTTPS.

## 4. Routenschutz & Mandanten-Check
- **`get_current_user(request)`** — lädt aktiven Nutzer aus `session["user_id"]`; fehlt/ungültig →
  HTML: Redirect `/login`; JSON: `401 not_authenticated`.
- **`get_current_customer(request, user)`** — liest `session["customer_id"]`, prüft
  `user ∈ customer` (über `user_customers`); nicht berechtigt/kein aktiver Kunde →
  `403 forbidden_customer` (bzw. Aufforderung zur Kundenwahl). **`customer_id`/Collection-Name
  werden nie aus Request-Parametern übernommen.**
- **Öffentlich:** `GET/POST /login`, `GET /api/health`, `/static/*`.
- **Geschützt + scoped:** `/`, `/api/documents*`, `/api/chat`, `/api/session/customer`, `/logout`.
- Login-Fehlermeldung **generisch** („E-Mail oder Passwort falsch") — keine User-Enumeration.

## 5. Nutzer- & Kundenverwaltung (Seed)
- Kein Self-Signup. Per Script:
  - `scripts/seed_customers.py` → Kunden (`acme`, `globex`, …) anlegen (idempotent).
  - `scripts/seed_users.py` → Nutzer (Argon2id-Hash) **plus** `user_customers`-Zuordnungen.
- Demo: mindestens **1 Nutzer mit 2 Kunden** (für Isolation-Demo) und ein Nutzer mit nur 1 Kunden
  (für Auto-Select-Pfad).

## 6. Datei-Upload-Sicherheit
- **Extension-Allowlist:** `.txt/.md/.pdf/.docx` (aus `ALLOWED_EXTENSIONS`); sonst `400`.
- **Größenlimit:** `MAX_UPLOAD_MB=30`; größer → `413`.
- **Filename-Sanitizing:** kein Path-Traversal (`..`, absolute Pfade, Slashes entfernen);
  Speicherpfad serverseitig aus `customer_id` + neuer `document_id` (UUID) gebaut, **nie** roher
  Dateiname als Pfad.
- **Extraktion robust:** leeres/kaputtes Dokument → `status=failed`, **nichts** in Qdrant (`422`).
- MIME/Extension werden geprüft; Inhalt wird nur als Text extrahiert (keine Ausführung).

## 7. Security-Checkliste (MVP)
| # | Maßnahme | Status |
|---|---|---|
| S1 | Passwörter nur als Argon2id-Hash | Pflicht |
| S2 | Generische Login-Fehlermeldung | Pflicht |
| S3 | Cookie `httponly`+`samesite=lax` | Pflicht |
| S4 | `SESSION_SECRET`+`OPENAI_API_KEY` Fail-fast | Pflicht |
| S5 | `.env` gitignored | Pflicht |
| S6 | API-Fehler ohne Stacktrace/Secret | Pflicht |
| S7 | Eingabevalidierung (Titel/Text/Message/Dateityp/-größe) | Pflicht |
| S8 | Keine Klartext-Logs von Passwörtern/Key | Pflicht |
| **S11** | **Jeder Ingest/Search/Chat/Delete prüft `user ∈ customer`** | **Pflicht (Invariant)** |
| **S12** | **Upload: Sanitizing, Max-Size, kein Path-Traversal** | **Pflicht** |
| S9 | `secure`-Cookie sobald HTTPS | bei Deployment |
| S10 | CSRF — siehe §8 | dokumentiert |

## 8. Bewusste Vereinfachungen & Restrisiken (MVP)
- **CSRF:** Bewusste Entscheidung — **kein** CSRF-Token-Mechanismus im MVP. Begründung: internes
  Tool hinter Login, `samesite=lax` + Session genügen für den Prototyp; Token-Maschinerie würde
  Scope kosten. **Als bekannte Lücke dokumentiert**, Roadmap: CSRF-Token für Formulare/Upload.
- **Rate-Limiting beim Login:** In-Memory-Sliding-Window (10 Fehlversuche / 60 s pro IP+E-Mail), blockt im Sperrfenster auch korrekte Passwörter, Reset nach Fensterablauf oder Erfolg. Ausreichend bei `--workers=1`; hinter Reverse-Proxy wirkt das Limit faktisch pro E-Mail (Proxy-IP). Umgesetzt 2026-06-09 (F5), nachgeschärft Runde 2.
- **Secrets at rest (AppSecret, LlmPreset.oauth_token etc. in SQLite):** bewusste Entscheidung für Self-Hosting-Szenario. Die DB-Datei liegt im Volume des Betreibers (`data/*.sqlite3`), Zugriffsschutz über Dateisystem-Rechte / Container-Isolation / Backup-Verschlüsselung (z. B. restic+passphrase oder LUKS). Keine zusätzliche App-seitige Verschlüsselung (würde Key-Management einführen und Self-Host-Hürde erhöhen). Risiko: bei kompromittiertem Host/Backup sind Secrets lesbar. Mitigation: strenge FS-Rechte, separate Backup-Verschlüsselung, kurze Rotation bei Verdacht, Dokumentation in `15_implementation_status.md`. (F7-Nachtrag 2026-06-09)
- **Kein RBAC:** Login + `user_customers` regeln *welche Kunden*; innerhalb eines Kunden keine
  Rollen. Inhaltliche Trennung **zwischen** Kunden ist hingegen Invariant (S11).
- **Transport:** lokal HTTP; produktiv TLS via Reverse-Proxy.

## 9. Später (Roadmap)
SSO (Entra/Okta — `get_current_user`/`get_current_customer` bleiben, nur Login-Schritt tauscht),
Rollen/Rechte, Audit-Log mit User+Customer, Login-Throttling, CSRF-Token, Secrets-Manager.
Siehe `12_roadmap.md`.
