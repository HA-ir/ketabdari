from datetime import datetime
import re
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: Optional[str] = Field(default=None, max_length=255)

    @field_validator("name")
    @classmethod
    def strip_and_validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Name cannot be empty or whitespace only")
        return stripped

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            return None
        if not EMAIL_REGEX.match(stripped):
            raise ValueError("Invalid email format")
        return stripped


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    email: Optional[str] = Field(default=None, max_length=255)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("Name cannot be empty or whitespace only")
        return stripped

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            return None
        if not EMAIL_REGEX.match(stripped):
            raise ValueError("Invalid email format")
        return stripped

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "UserUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided for update")
        return self


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: Optional[str] = None
    created_at: datetime


# Alias for backward compatibility
UserOut = UserRead
