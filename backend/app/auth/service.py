"""Auth business logic: registration, login, Google sign-in, sessions,
profile updates. Route handlers (app/api/routes/auth.py) stay thin and only
translate HTTP <-> these calls, matching the rest of TradeLens's
route/service separation.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.google_verify import verify_google_credential
from app.auth.models import AuthProvider, User, UserSession
from app.auth.security import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    generate_session_token,
    hash_password,
    hash_session_token,
    is_password_policy_satisfied,
    verify_password,
)
from app.core.exceptions import (
    EmailAlreadyRegisteredError,
    GoogleAccountCollisionError,
    InvalidCredentialsError,
    SessionInvalidError,
    WeakPasswordError,
)


def normalize_email(email: str) -> str:
    """Documented policy: trim whitespace, lowercase the ENTIRE address
    (local-part included) — see app.auth.models.User.email docstring for
    why this is a deliberate simplification, not full RFC 6531 handling."""
    return email.strip().lower()


def register_local(db: Session, *, full_name: str, display_name: str, email: str, password: str) -> User:
    if not is_password_policy_satisfied(password):
        raise WeakPasswordError(
            f"Password must be between {MIN_PASSWORD_LENGTH} and {MAX_PASSWORD_LENGTH} characters."
        )

    normalized_email = normalize_email(email)
    existing = db.scalar(select(User).where(User.email == normalized_email))
    if existing is not None:
        raise EmailAlreadyRegisteredError(normalized_email)

    user = User(
        email=normalized_email,
        password_hash=hash_password(password),
        full_name=full_name,
        display_name=display_name,
        auth_provider=AuthProvider.LOCAL,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_local(db: Session, *, email: str, password: str) -> User:
    normalized_email = normalize_email(email)
    user = db.scalar(select(User).where(User.email == normalized_email))

    # Constant-shape response regardless of which check failed, to avoid
    # account enumeration through error wording/timing shortcuts.
    if user is None or user.password_hash is None or not user.is_active:
        raise InvalidCredentialsError()
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError()
    return user


def authenticate_google(db: Session, *, credential: str, client_id: str) -> User:
    identity = verify_google_credential(credential, client_id)

    user = db.scalar(select(User).where(User.google_subject == identity.subject))
    if user is not None:
        return user

    normalized_email = normalize_email(identity.email)
    colliding_local_user = db.scalar(select(User).where(User.email == normalized_email))
    if colliding_local_user is not None:
        # colliding_local_user.google_subject is necessarily None here (a
        # matching google_subject would have returned above), so this is a
        # LOCAL-vs-GOOGLE email collision -> reject, do not auto-link.
        raise GoogleAccountCollisionError(normalized_email)

    user = User(
        email=normalized_email,
        google_subject=identity.subject,
        full_name=identity.full_name,
        display_name=identity.full_name,
        avatar_url=identity.avatar_url,
        auth_provider=AuthProvider.GOOGLE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_session(db: Session, user: User, *, ttl_days: int) -> str:
    raw_token = generate_session_token()
    session_row = UserSession(
        token_hash=hash_session_token(raw_token),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=ttl_days),
    )
    db.add(session_row)
    db.commit()
    return raw_token


def _as_aware_utc(value: datetime) -> datetime:
    """Normalize a datetime read back from the database to timezone-aware
    UTC before comparing. Postgres round-trips `DateTime(timezone=True)`
    as tz-aware; SQLite (used for the deterministic test suite) silently
    drops tzinfo and returns a naive datetime for the same column type —
    comparing a naive and an aware datetime raises TypeError. Values
    written by this codebase are always UTC to begin with (see `_utcnow`
    in models.py), so treating a naive value as UTC is correct here."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def get_user_for_session(db: Session, raw_token: str) -> User:
    token_hash = hash_session_token(raw_token)
    session_row = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash))

    now = datetime.now(timezone.utc)
    if (
        session_row is None
        or session_row.revoked_at is not None
        or _as_aware_utc(session_row.expires_at) < now
        or not session_row.user.is_active
    ):
        raise SessionInvalidError()

    return session_row.user


def revoke_session(db: Session, raw_token: str) -> None:
    token_hash = hash_session_token(raw_token)
    session_row = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash))
    if session_row is not None and session_row.revoked_at is None:
        session_row.revoked_at = datetime.now(timezone.utc)
        db.commit()


def update_profile(
    db: Session, user: User, *, full_name: str | None, display_name: str | None
) -> User:
    if full_name is not None:
        user.full_name = full_name
    if display_name is not None:
        user.display_name = display_name
    db.commit()
    db.refresh(user)
    return user
