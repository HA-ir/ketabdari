from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .rental import Rental

TZ_DT = DateTime(timezone=True)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Book(SQLModel, table=True):
    __tablename__ = "books"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True, max_length=300)
    author: Optional[str] = Field(default=None, max_length=200)
    quantity: int = Field(default=1, ge=0)
    created_at: datetime = Field(default_factory=_utcnow, sa_type=TZ_DT)

    rentals: list["Rental"] = Relationship(back_populates="book")
