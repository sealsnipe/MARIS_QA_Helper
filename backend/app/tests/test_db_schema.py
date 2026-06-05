from __future__ import annotations

from sqlalchemy import inspect, text

from app.db import _migrate_schema


def test_init_db_adds_deleted_at_to_legacy_documents_table(db_session, tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.sqlite3"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    from app import config, db

    config.get_settings.cache_clear()
    engine = db._create_engine(database_url)
    db.engine = engine
    db.SessionLocal = __import__("sqlalchemy.orm", fromlist=["sessionmaker"]).sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE documents (
                    id VARCHAR PRIMARY KEY,
                    customer_id VARCHAR NOT NULL,
                    title VARCHAR NOT NULL,
                    source_type VARCHAR NOT NULL DEFAULT 'manual',
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    status VARCHAR NOT NULL DEFAULT 'indexed',
                    created_at VARCHAR NOT NULL,
                    updated_at VARCHAR NOT NULL
                )
                """
            )
        )

    _migrate_schema(engine)
    columns = {col["name"] for col in inspect(engine).get_columns("documents")}
    assert "deleted_at" in columns


def test_init_db_adds_knowledge_content_review_columns(db_session, tmp_path, monkeypatch):
    db_path = tmp_path / "legacy_kc.sqlite3"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    from app import config, db

    config.get_settings.cache_clear()
    engine = db._create_engine(database_url)
    db.engine = engine
    db.SessionLocal = __import__("sqlalchemy.orm", fromlist=["sessionmaker"]).sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE knowledge_contents (
                    id VARCHAR PRIMARY KEY,
                    source_id VARCHAR NOT NULL,
                    title VARCHAR NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    keywords_json TEXT NOT NULL DEFAULT '[]',
                    content TEXT NOT NULL,
                    status VARCHAR NOT NULL DEFAULT 'pending',
                    created_at VARCHAR NOT NULL,
                    received_at VARCHAR NOT NULL
                )
                """
            )
        )

    _migrate_schema(engine)
    columns = {col["name"] for col in inspect(engine).get_columns("knowledge_contents")}
    assert "adopted_customer_id" in columns
    assert "reviewed_at" in columns
