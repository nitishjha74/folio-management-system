"""Authentication request/response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserPublic(BaseModel):
    """Safe user representation — never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str
    email: EmailStr
    full_name: str | None = None
    role: str
    is_active: bool
    created_at: datetime


class LoginResponse(BaseModel):
    user: UserPublic


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    full_name: str | None = Field(default=None, max_length=120)


class RegisterResponse(BaseModel):
    user: UserPublic