from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel

TZ_DT = DateTime(timezone=True)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserBase(SQLModel):
    name: str = Field(index=True, max_length=200)
    email: Optional[str] = Field(default=None, index=True, max_length=255)


class User(UserBase, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, sa_type=TZ_DT)

    rentals: list["Rental"] = Relationship(back_populates="user")


class BookBase(SQLModel):
    title: str = Field(index=True, max_length=300)
    author: Optional[str] = Field(default=None, max_length=200)
    quantity: int = Field(default=1, ge=0)


class Book(BookBase, table=True):
    __tablename__ = "books"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, sa_type=TZ_DT)

    rentals: list["Rental"] = Relationship(back_populates="book")


class RentalBase(SQLModel):
    user_id: int = Field(foreign_key="users.id", index=True)
    book_id: int = Field(foreign_key="books.id", index=True)
    due_date: datetime = Field(sa_type=TZ_DT)
    returned_at: Optional[datetime] = Field(default=None, sa_type=TZ_DT)


class Rental(RentalBase, table=True):
    __tablename__ = "rentals"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, sa_type=TZ_DT)

    user: Optional[User] = Relationship(back_populates="rentals")
    book: Optional[Book] = Relationship(back_populates="rentals")
