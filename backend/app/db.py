from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _create_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)

    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_wal(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


settings = get_settings()
engine = _create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _migrate_schema(engine) -> None:
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "users" in table_names:
        columns = {col["name"] for col in inspector.get_columns("users")}
        if "is_admin" not in columns:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
                )
    if "customers" in table_names:
        columns = {col["name"] for col in inspector.get_columns("customers")}
        if "active" not in columns:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE customers ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
                )
    if "documents" in table_names:
        columns = {col["name"] for col in inspector.get_columns("documents")}
        if "source_text" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE documents ADD COLUMN source_text TEXT"))
        if "extraction_meta" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE documents ADD COLUMN extraction_meta TEXT"))
        if "content_sha256" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE documents ADD COLUMN content_sha256 VARCHAR(64)"))
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_documents_content_sha256 "
                        "ON documents (customer_id, content_sha256)"
                    )
                )
    if "knowledge_contents" in table_names:
        columns = {col["name"] for col in inspector.get_columns("knowledge_contents")}
        migrations = {
            "original_content": "ALTER TABLE knowledge_contents ADD COLUMN original_content TEXT",
            "revision_json": "ALTER TABLE knowledge_contents ADD COLUMN revision_json TEXT",
            "refine_preset": "ALTER TABLE knowledge_contents ADD COLUMN refine_preset VARCHAR",
            "submitted_by": "ALTER TABLE knowledge_contents ADD COLUMN submitted_by VARCHAR",
        }
        for col, sql in migrations.items():
            if col not in columns:
                with engine.begin() as conn:
                    conn.execute(text(sql))


def init_db() -> None:
    import app.models  # noqa: F401 — register all ORM tables before create_all

    settings = get_settings()
    if settings.DATABASE_URL.startswith("sqlite:///./data/"):
        Path("data").mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _migrate_schema(engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
