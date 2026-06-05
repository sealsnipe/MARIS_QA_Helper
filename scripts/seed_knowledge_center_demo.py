#!/usr/bin/env python3
"""Seed Knowledge Center sources + sample content for local testing."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import SessionLocal, init_db
from app.knowledge_center import create_knowledge_source, get_source_by_host_code, ingest_knowledge_contents


DEMO_SOURCES: tuple[tuple[str, str], ...] = (
    ("Demo Agent", "demo-agent"),
    ("Jira Sync (Mock)", "jira-sync"),
)

DEMO_ITEMS: tuple[dict, ...] = (
    {
        "title": "VPN-Verbindung bricht ab — Checkliste",
        "summary": "Typische Ursachen und Schritte bei instabiler VPN-Verbindung im Homeoffice.",
        "content": (
            "Prüfen Sie zuerst die Internetverbindung ohne VPN. Starten Sie den VPN-Client neu "
            "und löschen Sie gespeicherte Profile bei wiederholten Timeouts. Firewall-Regeln "
            "müssen UDP 500/4500 und ESP erlauben."
        ),
        "keywords": ["vpn", "netzwerk", "homeoffice"],
        "source_ref": "https://example.internal/kb/vpn-checklist",
        "customer_id": "bg-ludwigshafen",
        "external_id": "demo-vpn-1",
    },
    {
        "title": "Passwort-Reset für Active Directory",
        "summary": "Anleitung für Helpdesk: AD-Passwort zurücksetzen und Erstlogin erzwingen.",
        "content": (
            "Im AD-Users-and-Computers das Konto öffnen, Rechtsklick Reset Password. "
            "Option 'User must change password at next logon' aktivieren. "
            "Temporäres Passwort per sicherem Kanal übermitteln."
        ),
        "keywords": ["ad", "passwort", "helpdesk"],
        "source_ref": "AD-HOWTO-042",
        "customer_id": "bg-ludwigshafen",
        "external_id": "demo-ad-reset",
    },
    {
        "title": "Allgemeiner IT-Sicherheitshinweis: Phishing",
        "summary": "Kurzinfo zu Phishing-Mails — ohne festen Mandantenbezug.",
        "content": (
            "Verdächtige Absender, Druck zur Sofortreaktion und ungewöhnliche Links sind Warnsignale. "
            "Niemals Anhänge öffnen oder Links folgen ohne Absenderprüfung. "
            "Verdachtsfälle an die Security-Adresse melden."
        ),
        "keywords": ["security", "phishing"],
        "source_ref": "SEC-BULLETIN-2026-01",
        "external_id": "demo-phishing",
    },
    {
        "title": "Ticket KKRR-8842: Drucker offline",
        "summary": "Aus Jira-Sync: Netzwerkdrucker antwortet nicht im Standort Düsseldorf.",
        "content": (
            "Drucker HP-LJ-402 im VLAN Druck. Ping fehlgeschlagen. Switch-Port geprüft — Link up. "
            "Neustart des Druckservers PrintSrv02 behob das Problem. "
            "Monitoring-Alert für Print-Spooler eingerichtet."
        ),
        "keywords": ["drucker", "jira", "kkrr"],
        "source_ref": "KKRR-8842",
        "customer_id": "kkrr",
        "external_id": "KKRR-8842",
    },
)


def main() -> None:
    init_db()
    with SessionLocal() as db:
        for name, host_code in DEMO_SOURCES:
            if get_source_by_host_code(db, host_code) is None:
                create_knowledge_source(db, name, host_code)
                print(f"  + Source: {name} ({host_code})")
            else:
                print(f"  ○ Source existiert: {host_code}")

        result = ingest_knowledge_contents(
            db,
            "demo-agent",
            list(DEMO_ITEMS[:3]),
        )
        print(f"  demo-agent ingest: {result}")

        result2 = ingest_knowledge_contents(
            db,
            "jira-sync",
            [DEMO_ITEMS[3]],
        )
        print(f"  jira-sync ingest: {result2}")

    print("")
    print("Demo bereit:")
    print("  UI:  http://127.0.0.1:8090/tools/knowledge-center")
    print("  Sources (Admin): http://127.0.0.1:8090/tools/knowledge-center/sources")
    token = os.environ.get("INTEGRATION_API_TOKEN", "").strip()
    if token:
        print("")
        print("  Ingest testen:")
        print(f'  curl -s -X POST http://127.0.0.1:8090/api/v1/knowledge-content \\')
        print(f'    -H "Authorization: Bearer {token[:8]}…" \\')
        print('    -H "Content-Type: application/json" \\')
        print('    -d \'{"host_code":"demo-agent","items":[{"title":"Neu aus curl","summary":"Test","content":"Mindestens zwanzig Zeichen Inhalt hier.","external_id":"curl-test-1"}]}\'')


if __name__ == "__main__":
    main()
