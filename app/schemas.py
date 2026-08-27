from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _ensure_aware(v: datetime) -> datetime:
    if v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


# ---------- Requests ----------

class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: Optional[str] = Field(default=None, max_length=255)


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    email: Optional[str] = Field(default=None, max_length=255)

    @classmethod
    def validate_partial(cls, data: dict) -> dict:
        return {k: v for k, v in data.items() if v is not None}


class BookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    author: Optional[str] = Field(default=None, max_length=200)


class BookUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    author: Optional[str] = Field(default=None, max_length=200)


class RentalCreate(BaseModel):
    user_id: int
    book_id: int
    due_date: datetime

    @field_validator("due_date")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        return _ensure_aware(v)


# ---------- Response briefs ----------

class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class BookBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str


# ---------- Response models ----------

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: Optional[str]
    created_at: datetime


class BookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    author: Optional[str]
    created_at: datetime


class RentalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    book_id: int
    due_date: datetime
    returned_at: Optional[datetime]
    created_at: datetime
    user: Optional[UserBrief] = None
    book: Optional[BookBrief] = None


class PaginatedBooks(BaseModel):
    items: list[BookOut]
    total: int
    page: int
    size: int
    pages: int