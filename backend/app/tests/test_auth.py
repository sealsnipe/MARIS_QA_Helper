from app.auth import hash_password, verify_password


def test_hash_verify_roundtrip():
    password = "GeheimesPW!"
    password_hash = hash_password(password)
    assert verify_password(password_hash, password)
    assert password_hash != password


def test_verify_rejects_wrong_password():
    password_hash = hash_password("correct")
    assert not verify_password(password_hash, "wrong")


def test_two_hashes_differ():
    first = hash_password("same-password")
    second = hash_password("same-password")
    assert first != second


def test_get_current_user_without_session_returns_401(client):
    response = client.get("/api/me")
    assert response.status_code == 401
    assert response.json() == {"error": "not_authenticated"}


def test_protected_html_redirects_to_login(client):
    response = client.get("/chat", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_login_failure_shows_generic_error(client, db_session):
    from app.tests.conftest import create_user

    create_user(db_session, "user@example.com", "correct-password")

    response = client.post(
        "/login",
        data={"email": "user@example.com", "password": "wrong-password"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/login?error=1"

    page = client.get("/login?error=1")
    assert "E-Mail oder Passwort falsch" in page.text


def test_login_success_sets_session(client, db_session):
    from app.tests.conftest import create_customer, create_user, login

    create_customer(db_session, "kkrr", "Katholische Kliniken Rhein Ruhr")
    create_user(db_session, "single@example.com", "secret123", ("kkrr",))
    login(client, "single@example.com", "secret123")

    response = client.get("/api/me")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "single@example.com"
    assert body["active_customer"] == "kkrr"


def test_logout_clears_session(client, db_session):
    from app.tests.conftest import create_customer, create_user, login

    create_customer(db_session, "kkrr", "Katholische Kliniken Rhein Ruhr")
    create_user(db_session, "single@example.com", "secret123", ("kkrr",))
    login(client, "single@example.com", "secret123")

    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 302
    assert client.get("/api/me").status_code == 401


def test_login_rate_limit_blocks_correct_password_in_window(client, db_session):
    """Core of N1 fix: after 10 fails, even a correct password on the 11th attempt
    must be rate_limited (no verify_password happens for locked keys).
    """
    from app.tests.conftest import create_user
    from app import routes as routes_mod

    routes_mod._login_failures.clear()
    create_user(db_session, "rate@example.com", "correct-pw")

    # 10 fails with wrong pw
    for _ in range(10):
        r = client.post(
            "/login",
            data={"email": "rate@example.com", "password": "wrong"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        assert "error=1" in r.headers["location"]

    # 11th attempt with CORRECT password must still be rate_limited
    r11 = client.post(
        "/login",
        data={"email": "rate@example.com", "password": "correct-pw"},
        follow_redirects=False,
    )
    assert r11.status_code == 302
    assert "error=rate_limited" in r11.headers["location"]

    page = client.get("/login?error=rate_limited")
    assert "Zu viele Fehlversuche" in page.text

    routes_mod._login_failures.clear()


def test_login_rate_limit_reset_after_window_or_success(client, db_session):
    """Window expiry or success must reset the counter so next correct login works."""
    from app.tests.conftest import create_user
    from app import routes as routes_mod
    import time as _time

    routes_mod._login_failures.clear()
    create_user(db_session, "rate@example.com", "correct-pw")

    # Cause 5 fails
    for _ in range(5):
        client.post(
            "/login",
            data={"email": "rate@example.com", "password": "wrong"},
            follow_redirects=False,
        )

    # Artificially expire the window for this key (backdate timestamps)
    key = next((k for k in routes_mod._login_failures if k[1] == "rate@example.com"), None)
    if key:
        old_ts = routes_mod._login_failures[key]
        routes_mod._login_failures[key] = [t - 61 for t in old_ts]

    # Correct password after expiry must succeed and pop the key
    r_ok = client.post(
        "/login",
        data={"email": "rate@example.com", "password": "correct-pw"},
        follow_redirects=False,
    )
    assert r_ok.status_code == 302
    assert "/chat" in (r_ok.headers.get("location") or "")
    assert key not in routes_mod._login_failures or len(routes_mod._login_failures.get(key, [])) == 0

    routes_mod._login_failures.clear()


def test_login_rate_limit_pruning(client, db_session):
    """Global prune when > PRUNE_THRESHOLD old entries; a request causes shrink."""
    from app import routes as routes_mod
    from app.tests.conftest import create_user
    import time as _time

    routes_mod._login_failures.clear()
    create_user(db_session, "prune@example.com", "pw")

    # Inject many expired entries to exceed threshold
    now = _time.time()
    for i in range(routes_mod._LOGIN_RATE_PRUNE_THRESHOLD + 50):
        fake_key = (f"ip{i}", f"spam{i}@example.com")
        routes_mod._login_failures[fake_key] = [now - 100]  # all expired

    assert len(routes_mod._login_failures) > routes_mod._LOGIN_RATE_PRUNE_THRESHOLD

    # A normal (even failing) request should trigger prune on entry
    client.post(
        "/login",
        data={"email": "prune@example.com", "password": "wrong"},
        follow_redirects=False,
    )

    # After prune the dict must have shrunk (old spam keys removed)
    assert len(routes_mod._login_failures) <= routes_mod._LOGIN_RATE_PRUNE_THRESHOLD + 5

    routes_mod._login_failures.clear()
