"""Password hashing and session-token generation/hashing.

Password hashing: Argon2id via `argon2-cffi` (the reference Argon2
implementation's Python bindings), not a hand-rolled scheme and not
MD5/SHA1/plain-SHA256. Default cost parameters from `argon2.PasswordHasher`
are used — they are already tuned to a reasonable modern baseline (RFC 9106
low-memory-ish profile) rather than picking arbitrary numbers ourselves.

Session tokens: a cryptographically random opaque value (`secrets.token_urlsafe`)
is what actually goes in the cookie. Only its SHA-256 hash is ever persisted,
so a stolen database dump cannot be replayed as a working session cookie.
This is a fixed-value hash (not a slow password-style hash) because the
token itself already has ~256 bits of entropy — it doesn't need brute-force
resistance the way a human-chosen password does.
"""

from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

_password_hasher = PasswordHasher()

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def is_password_policy_satisfied(password: str) -> bool:
    return MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH


def generate_session_token() -> str:
    """The raw, high-entropy value that goes in the cookie."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """The value actually stored/queried in the database."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
