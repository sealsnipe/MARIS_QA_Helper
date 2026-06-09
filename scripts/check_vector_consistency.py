#!/usr/bin/env python3
"""Konsistenz-Check (und Repair) zwischen SQLite und Qdrant.

Vergleicht pro Document die Chunk-Zeilen in SQLite mit den tatsächlichen
Chunk-Punkten in Qdrant (Fingerprint-Punkte werden korrekt ausgenommen).

Usage (aus dem Projekt-Root):
  python3 scripts/check_vector_consistency.py                  # alle aktiven Kunden
  python3 scripts/check_vector_consistency.py global           # nur ein Kunde
  python3 scripts/check_vector_consistency.py --orphans        # zusätzlich Orphan-Punkte suchen
  python3 scripts/check_vector_consistency.py --repair         # Mismatches per Re-Index reparieren
  python3 scripts/check_vector_consistency.py --orphans --repair-orphans   # Orphan-Punkte löschen

--repair re-embedded die betroffenen Dokumente (braucht Embedding-API-Key).
Exit-Code 1, wenn nach dem Lauf noch Inkonsistenzen offen sind.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.config import get_settings
from app.customers import collection_name
from app.db import SessionLocal
from app.document_fingerprints import FINGERPRINT_KIND
from app.models import Chunk, Customer, Document


def _chunk_points_filter(document_id: str) -> qmodels.Filter:
    """Nur echte Chunk-Punkte zählen — Fingerprint-Punkte tragen dieselbe document_id."""
    return qmodels.Filter(
        must=[
            qmodels.FieldCondition(key="document_id", match=qmodels.MatchValue(value=document_id)),
        ],
        must_not=[
            qmodels.FieldCondition(key="kind", match=qmodels.MatchValue(value=FINGERPRINT_KIND)),
        ],
    )


def count_chunk_points(client: QdrantClient, collection: str, document_id: str) -> int:
    try:
        return client.count(
            collection_name=collection,
            count_filter=_chunk_points_filter(document_id),
            exact=True,
        ).count
    except Exception as exc:
        print(f"  [warn] Qdrant count failed for {document_id}: {exc}", file=sys.stderr)
        return -1


def find_orphan_points(client: QdrantClient, collection: str, live_document_ids: set[str]) -> list:
    """Punkte (Chunks und Fingerprints), deren document_id kein lebendes Document mehr hat."""
    orphans = []
    offset = None
    while True:
        records, offset = client.scroll(
            collection_name=collection,
            offset=offset,
            limit=256,
            with_payload=True,
            with_vectors=False,
        )
        for rec in records:
            payload = rec.payload or {}
            document_id = payload.get("document_id")
            if document_id and document_id not in live_document_ids:
                orphans.append(rec)
        if offset is None:
            break
    return orphans


def delete_points(client: QdrantClient, collection: str, point_ids: list) -> None:
    for start in range(0, len(point_ids), 256):
        client.delete(
            collection_name=collection,
            points_selector=qmodels.PointIdsList(points=point_ids[start : start + 256]),
        )


def check_customer(
    db,
    client: QdrantClient,
    customer_id: str,
    *,
    prefix: str,
    check_orphans: bool,
    repair: bool,
    repair_orphans: bool,
) -> tuple[int, int]:
    """Returns (checked_docs, remaining_issues)."""
    collection = collection_name(customer_id, prefix=prefix)
    collection_exists = client.collection_exists(collection)

    docs = (
        db.query(Document)
        .filter(Document.customer_id == customer_id, Document.deleted_at.is_(None))
        .order_by(Document.created_at.desc())
        .all()
    )

    if not collection_exists and not docs:
        print(f"[{customer_id}] Keine Collection {collection} und keine Dokumente — ok.")
        return 0, 0

    print(f"\n[{customer_id}] Collection {collection}" + ("" if collection_exists else " FEHLT (alle Dokumente unindexiert!)"))

    mismatched_docs: list[Document] = []
    for doc in docs:
        sqlite_count = db.query(Chunk).filter(Chunk.document_id == doc.id).count()
        if doc.chunk_count and doc.chunk_count != sqlite_count:
            print(f"  [note] doc.chunk_count={doc.chunk_count}, tatsächliche Chunk-Zeilen={sqlite_count} für {doc.id}")

        qdrant_count = count_chunk_points(client, collection, doc.id) if collection_exists else 0
        if qdrant_count < 0:
            continue
        if sqlite_count != qdrant_count:
            mismatched_docs.append(doc)
            print(f"  MISMATCH {doc.id} {doc.title[:60]!r}")
            print(f"    sqlite_chunks={sqlite_count}  qdrant_points={qdrant_count}  status={doc.status}")

    print(f"  {len(docs)} Dokumente geprüft, {len(mismatched_docs)} Mismatches.")

    issues = len(mismatched_docs)
    if repair and mismatched_docs:
        from app.ingestion import IngestionError, reindex_document

        for doc in mismatched_docs:
            try:
                result = reindex_document(db, customer_id, doc.id)
                print(f"  REPARIERT {doc.id} → {result.document.chunk_count} Chunks neu indexiert.")
                issues -= 1
            except IngestionError as exc:
                db.rollback()
                print(f"  REPAIR FEHLGESCHLAGEN {doc.id}: {exc.code} {exc.detail or ''}", file=sys.stderr)

    if check_orphans and collection_exists:
        live_ids = {d.id for d in docs}
        try:
            orphans = find_orphan_points(client, collection, live_ids)
        except Exception as exc:
            print(f"  [warn] Orphan-Scan fehlgeschlagen: {exc}", file=sys.stderr)
            orphans = []
        if orphans:
            for rec in orphans[:5]:
                payload = rec.payload or {}
                kind = payload.get("kind") or "chunk"
                print(f"    orphan point id={rec.id} kind={kind} document_id={payload.get('document_id')}")
            print(f"  {len(orphans)} Orphan-Punkte gefunden (max. 5 angezeigt).")
            if repair_orphans:
                delete_points(client, collection, [rec.id for rec in orphans])
                print(f"  {len(orphans)} Orphan-Punkte gelöscht.")
            else:
                issues += len(orphans)
        else:
            print("  Keine Orphan-Punkte.")

    return len(docs), issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Konsistenz-Check SQLite vs. Qdrant pro Dokument.")
    parser.add_argument("customer", nargs="?", default=None, help="Bestimmte customer_id (Default: alle aktiven)")
    parser.add_argument("--all", action="store_true", help="Alle aktiven Kunden prüfen (Default ohne customer-Argument)")
    parser.add_argument("--orphans", action="store_true", help="Zusätzlich Orphan-Punkte in Qdrant suchen")
    parser.add_argument("--repair", action="store_true", help="Mismatches per Re-Index (delete + neu embedden) reparieren")
    parser.add_argument("--repair-orphans", action="store_true", help="Gefundene Orphan-Punkte aus Qdrant löschen (impliziert --orphans)")
    args = parser.parse_args()

    if args.repair_orphans:
        args.orphans = True

    settings = get_settings()
    client = QdrantClient(url=settings.QDRANT_URL, timeout=30)
    db = SessionLocal()

    try:
        if args.all or args.customer is None:
            customer_ids = [c.id for c in db.query(Customer).filter(Customer.active == 1).all()]
        else:
            customer_ids = [args.customer]

        total_issues = 0
        for cid in customer_ids:
            _, issues = check_customer(
                db,
                client,
                cid,
                prefix=settings.COLLECTION_PREFIX,
                check_orphans=args.orphans,
                repair=args.repair,
                repair_orphans=args.repair_orphans,
            )
            total_issues += issues

        print(f"\nOffene Inkonsistenzen über alle geprüften Kunden: {total_issues}")
        return 1 if total_issues else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
