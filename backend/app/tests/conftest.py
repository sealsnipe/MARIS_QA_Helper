import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Test env must be set before app imports that read settings.
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-for-pytest-only")

from app.auth import hash_password
from app.customers import validate_customer_slug
from app.db import SessionLocal, get_db, init_db
from app.embeddings import set_embeddings_backend
from app.main import app
from app.models import Customer, User, UserCustomer, utc_now_iso
from app.qdrant_store import InMemoryVectorStore, set_vector_store


class FakeEmbeddings:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.01] * 1536 for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.01] * 1536


@pytest.fixture()
def fake_embeddings():
    backend = FakeEmbeddings()
    set_embeddings_backend(backend)
    yield backend
    set_embeddings_backend(None)


@pytest.fixture()
def fake_vector_store():
    store = InMemoryVectorStore(vector_dim=1536)
    set_vector_store(store)
    yield store
    set_vector_store(None)


@pytest.fixture(autouse=True)
def _auto_mock_ai(fake_embeddings, fake_vector_store):
    yield


@pytest.fixture()
def db_session(tmp_path, monkeypatch) -> Generator[Session, None, None]:
    db_path = tmp_path / "test.sqlite3"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    from app import config, db

    config.get_settings.cache_clear()
    new_engine = db._create_engine(database_url)
    db.engine = new_engine
    db.SessionLocal = __import__("sqlalchemy.orm", fromlist=["sessionmaker"]).sessionmaker(
        bind=new_engine,
        autoflush=False,
        autocommit=False,
    )
    init_db()
    session = db.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        new_engine.dispose()
        config.get_settings.cache_clear()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_customer(db: Session, customer_id: str, name: str) -> Customer:
    customer = Customer(id=customer_id, name=name, created_at=utc_now_iso())
    db.add(customer)
    db.commit()
    return customer


def create_user(
    db: Session,
    email: str,
    password: str = "secret123",
    customer_ids: tuple[str, ...] = (),
    *,
    is_admin: bool = False,
) -> User:
    user = User(
        id=f"user-{email.split('@')[0]}",
        email=email.lower(),
        password_hash=hash_password(password),
        is_active=1,
        is_admin=1 if is_admin else 0,
        created_at=utc_now_iso(),
    )
    db.add(user)
    db.flush()
    for customer_id in customer_ids:
        if not validate_customer_slug(customer_id):
            raise ValueError(customer_id)
        db.add(UserCustomer(user_id=user.id, customer_id=customer_id))
    db.commit()
    db.refresh(user)
    return user


def login(client: TestClient, email: str, password: str) -> None:
    response = client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )
    assert response.status_code == 302
