from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .common import Page


class BookBase(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    author: Optional[str] = Field(default=None, max_length=200)
    quantity: int = Field(default=1, ge=0, le=100000)

    @field_validator("title")
    @classmethod
    def strip_and_validate_title(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Title cannot be empty or whitespace only")
        return stripped

    @field_validator("author")
    @classmethod
    def strip_author(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None


class BookCreate(BookBase):
    pass


class BookUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    author: Optional[str] = Field(default=None, max_length=200)
    quantity: Optional[int] = Field(default=None, ge=0, le=100000)

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("Title cannot be empty or whitespace only")
        return stripped

    @field_validator("author")
    @classmethod
    def strip_author(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "BookUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided for update")
        return self


class BookBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str


class BookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    author: Optional[str] = None
    quantity: int
    created_at: datetime


BookOut = BookRead
PaginatedBooks = Page[BookRead]
