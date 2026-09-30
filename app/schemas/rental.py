from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .book import BookBrief, BookRead
from .common import Page
from .user import UserBrief


def _ensure_aware(v: datetime) -> datetime:
    if v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


class RentalCreate(BaseModel):
    user_id: int = Field(gt=0)
    book_id: int = Field(gt=0)
    due_date: datetime

    @field_validator("due_date")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        return _ensure_aware(v)


class RentalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    book_id: int
    due_date: datetime
    returned_at: Optional[datetime] = None
    created_at: datetime
    user: Optional[UserBrief] = None
    book: Optional[BookBrief] = None


RentalOut = RentalRead


class UserRentalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    rental_id: int
    user_id: int
    book_id: int
    status: str  # "active" | "returned" | "overdue"
    created_at: datetime  # rental date
    due_date: datetime
    returned_at: Optional[datetime] = None
    book: BookRead
    user: Optional[UserBrief] = None


PaginatedUserRentals = Page[UserRentalRead]
