from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .book import Book
    from .user import User

TZ_DT = DateTime(timezone=True)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Rental(SQLModel, table=True):
    __tablename__ = "rentals"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    book_id: int = Field(foreign_key="books.id", index=True)
    due_date: datetime = Field(sa_type=TZ_DT)
    returned_at: Optional[datetime] = Field(default=None, sa_type=TZ_DT)
    created_at: datetime = Field(default_factory=_utcnow, sa_type=TZ_DT)

    user: Optional["User"] = Relationship(back_populates="rentals")
    book: Optional["Book"] = Relationship(back_populates="rentals")
