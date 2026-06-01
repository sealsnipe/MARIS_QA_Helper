from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    customers: Mapped[list["Customer"]] = relationship(
        secondary="user_customers",
        back_populates="users",
    )


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    users: Mapped[list[User]] = relationship(
        secondary="user_customers",
        back_populates="customers",
    )


class UserCustomer(Base):
    __tablename__ = "user_customers"

    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String, ForeignKey("customers.id"), primary_key=True)
