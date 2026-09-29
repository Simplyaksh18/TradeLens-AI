"""User/session persistence models.

Scope for Phase 1G (see CLAUDE.md): users, authentication identity, profile
data only. Market-data cache stays on the filesystem — unchanged.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class AuthProvider(str, enum.Enum):
    LOCAL = "LOCAL"
    GOOGLE = "GOOGLE"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # Normalization policy (documented, not a full RFC 6531 implementation):
    # trimmed and lowercased in full (local-part included). This is a
    # pragmatic simplification — real mail systems overwhelmingly treat the
    # local-part case-insensitively too — not a byte-for-byte spec-exact
    # normalization. Enforced in app.auth.service.normalize_email, not here.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)

    # NULL for GOOGLE-only accounts. Never plaintext — see app.auth.security.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Google's stable, verified `sub` claim — NOT the Google email, so a
    # user changing their Google account email doesn't orphan the link.
    # Unique when present; Postgres/SQLite both allow multiple NULLs under
    # a UNIQUE constraint, so LOCAL users (google_subject=NULL) don't collide.
    google_subject: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)

    full_name: Mapped[str] = mapped_column(String(200))
    display_name: Mapped[str] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    auth_provider: Mapped[AuthProvider] = mapped_column(Enum(AuthProvider, name="auth_provider"))
    is_active: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    """Server-side session row. The cookie carries only a random opaque
    token; this table stores a SHA-256 hash of that token (never the raw
    token itself), so a database compromise alone doesn't yield usable
    session cookies. See app.auth.security for hashing/generation."""

    __tablename__ = "user_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")
