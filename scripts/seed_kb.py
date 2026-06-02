#!/usr/bin/env python3
"""Seed demo knowledge per customer via ingest_text (requires OPENAI_API_KEY + Qdrant)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.db import SessionLocal, init_db
from app.ingestion import IngestionError, ingest_text
from seed_data import DEMO_CUSTOMERS, PRODUCTION_CUSTOMERS

# Deutlich unterscheidbare Demo-Inhalte je Mandant (Isolation sichtbar).
KB_ENTRIES: tuple[tuple[str, str, str], ...] = (
    (
        "bg-ludwigshafen",
        "BG Ludwigshafen — VPN Runbook",
        "BG Ludwigshafen: VPN-Probleme werden zuerst am FortiGate in Ludwigshafen geprüft. "
        "Eskalation nach 15 Minuten an das BG-Ludwigshafen Netzwerkteam. Hotline intern 4201.",
    ),
    (
        "bg-frankfurt",
        "BG Frankfurt — Firewall FAQ",
        "BG Frankfurt: Neue Firewall-Regeln werden ausschließlich über das Frankfurter Change-Portal "
        "beantragt. Standard-Freigabe dauert 2 Werktage. Notfall-Eskalation: Team Firewall Frankfurt.",
    ),
    (
        "detmold-lippe",
        "Detmold Lippe — Citrix Leitfaden",
        "Detmold Lippe: Citrix-Sitzungen werden über den Detmold-Lippe Broker neu gestartet. "
        "Bei Profilfehlern den Ordner unter \\\\dl-share\\profiles leeren und neu anmelden.",
    ),
    (
        "kkrr",
        "KKRR — Klinik IT Support",
        "Katholische Kliniken Rhein Ruhr: Klinik-IT Support erfolgt über das KKRR Ticketportal. "
        "Medizingeräte-Netzwerk ist getrennt — niemals Geräte im Patienten-WLAN registrieren.",
    ),
    (
        "acme",
        "Acme VPN Runbook (Demo)",
        "Acme GmbH Demo: VPN Reset über acme-vpn.example.com — nur für Isolationstests.",
    ),
    (
        "globex",
        "Globex Firewall FAQ (Demo)",
        "Globex AG Demo: Firewall-Änderungen nur via globex-fw.example.com — Isolationstest-Inhalt.",
    ),
)


def seed_kb(entries: tuple[tuple[str, str, str], ...] = KB_ENTRIES) -> None:
    init_db()
    with SessionLocal() as db:
        for customer_id, title, text in entries:
            try:
                result = ingest_text(
                    db,
                    customer_id=customer_id,
                    title=title,
                    text=text,
                    source_type="manual",
                )
                print(
                    f"Indexed {customer_id}: {title} "
                    f"({result.document.chunk_count} chunks, id={result.document.id})"
                )
            except IngestionError as exc:
                print(f"FAILED {customer_id} / {title}: {exc.code} {exc.detail or ''}")


if __name__ == "__main__":
    print("Seeding KB for production customers:", ", ".join(c[0] for c in PRODUCTION_CUSTOMERS))
    print("and demo customers:", ", ".join(c[0] for c in DEMO_CUSTOMERS))
    seed_kb()
