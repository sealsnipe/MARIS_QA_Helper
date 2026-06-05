from __future__ import annotations

import re

from app.customers import deactivate_tenant_customer, ensure_global_customer
from app.tests.conftest import create_customer, create_user, login


def _boot_field(html: str, field: str) -> str:
    match = re.search(rf'{field}:\s*(.+?),\n', html)
    assert match, f"{field} missing in APP_BOOT"
    return match.group(1).strip().strip('"')


def test_chat_page_boot_reflects_session_customer(client, db_session):
    ensure_global_customer(db_session)
    create_customer(db_session, "bg-frankfurt", "BG Frankfurt")
    create_user(db_session, "user@example.com", "secret123", ("bg-frankfurt",))
    login(client, "user@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-frankfurt"})

    response = client.get("/chat")
    assert response.status_code == 200
    html = response.text
    assert 'value="bg-frankfurt"' in html
    assert re.search(r'value="bg-frankfurt"[^>]*selected', html)
    assert _boot_field(html, "activeCustomerId") == "bg-frankfurt"
    assert _boot_field(html, "customerNavMode") == "scoped"


def test_global_nav_page_does_not_fake_select_global_without_session(client, db_session):
    ensure_global_customer(db_session)
    create_customer(db_session, "bg-frankfurt", "BG Frankfurt")
    create_customer(db_session, "kkrr", "KKRR")
    create_user(db_session, "user@example.com", "secret123", ("bg-frankfurt", "kkrr"))
    login(client, "user@example.com", "secret123")

    response = client.get("/tools/knowledge-center/submit")
    assert response.status_code == 200
    html = response.text
    assert _boot_field(html, "customerNavMode") == "global"
    assert _boot_field(html, "activeCustomerId") == ""
    assert 'value="global"' in html
    assert not re.search(r'value="global"[^>]*selected', html)


def test_invalid_session_customer_cleared_on_chat_page(client, db_session):
    ensure_global_customer(db_session)
    create_customer(db_session, "bg-frankfurt", "BG Frankfurt")
    create_user(db_session, "user@example.com", "secret123", ("bg-frankfurt",))
    login(client, "user@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-frankfurt"})
    deactivate_tenant_customer(db_session, "bg-frankfurt")

    response = client.get("/chat")
    assert response.status_code == 200
    assert _boot_field(response.text, "activeCustomerId") == ""
