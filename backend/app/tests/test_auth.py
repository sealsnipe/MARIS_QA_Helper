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

    create_customer(db_session, "globex", "Globex AG")
    create_user(db_session, "single@example.com", "secret123", ("globex",))
    login(client, "single@example.com", "secret123")

    response = client.get("/api/me")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "single@example.com"
    assert body["active_customer"] == "globex"


def test_logout_clears_session(client, db_session):
    from app.tests.conftest import create_customer, create_user, login

    create_customer(db_session, "globex", "Globex AG")
    create_user(db_session, "single@example.com", "secret123", ("globex",))
    login(client, "single@example.com", "secret123")

    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 302
    assert client.get("/api/me").status_code == 401
