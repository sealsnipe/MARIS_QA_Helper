# `backend/app/templates/login.html`

**Quellpfad:** `backend/app/templates/login.html`

## Zweck und logischer Aufbau

Jinja2-Template für die **Anmeldeseite**. Es erweitert das schlanke `base.html` und rendert eine zentrierte Login-Karte mit Markenbanner, Fehlermeldung (optional) und POST-Formular für E-Mail und Passwort.

Authentifizierung erfolgt **serverseitig** über `POST /login` in `routes.py` (kein JavaScript nötig). Bei bereits aktiver Session leitet `GET /login` direkt nach `/chat` um. Bei falschen Zugangsdaten erfolgt Redirect auf `/login?error=1`, wodurch das Template `error` gesetzt bekommt.

Lesereihenfolge: Markenbereich → Untertitel → optionaler Fehler → Formular mit zwei Feldern und Submit.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `base.html`; `/static/brand-banner.svg`
- **Wird genutzt von:** `backend/app/routes.py` — `login_form` (`GET /login`)
- **HTTP / UI / CLI:**
  - `GET /login` — Formular anzeigen
  - `POST /login` — Anmeldung (`email`, `password` als Form-Felder)
  - Erfolg → Redirect `/chat`; Fehler → `/login?error=1`
- **Daten:** SQLite `User`; Session erhält `user_id` und ggf. `customer_id` (bei genau einem Kunden)

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `title` | Jinja-Block | Browser-Titel: „Anmelden — MARIS - Q/A Helper“ |
| `content` | Jinja-Block | Login-Karte mit Formular |

### Jinja-Kontext

| Name | Art | Beschreibung |
|---|---|---|
| `error` | `str` \| None | Gesetzt bei Query `?error=1` — zeigt Fehlermeldung |

## Funktionen und Klassen

Keine — statisches Formular-Template ohne Client-Logik.

## HTML / JS / CSS — zusätzliche Hinweise

- **extends:** `base.html` — kein `app.js`, kein `APP_BOOT`
- **Formular:** `method="post"`, `action="/login"`, Klasse `form`
- **Felder:**
  - `name="email"`, `type="email"`, `autocomplete="username"`, required
  - `name="password"`, `type="password"`, `autocomplete="current-password"`, required
- **Fehleranzeige:** `{% if error %}` → `<p class="error" role="alert">E-Mail oder Passwort falsch.</p>`
- **CSS-Klassen:** `card`, `login-card`, `login-brand`, `login-brand-banner`, `subtitle`
- **Barrierefreiheit:** `role="alert"` auf Fehlertext
