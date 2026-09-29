from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field

from app.auth.models import AuthProvider, User


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)  # exact bounds enforced in service (documented policy)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class GoogleAuthRequest(BaseModel):
    credential: str = Field(min_length=1)


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    display_name: str | None = Field(default=None, min_length=1, max_length=100)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    display_name: str
    avatar_url: str | None
    auth_provider: AuthProvider

    @classmethod
    def from_domain(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            auth_provider=user.auth_provider,
        )
