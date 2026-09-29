"""Cryptographic verification of a Google Identity Services credential.

CRITICAL (see CLAUDE.md Phase 1G): TradeLens must never trust an email/name/
picture/subject merely because the frontend sent them. Every field used here
comes only from `google.oauth2.id_token.verify_oauth2_token`, which:
  - verifies the JWT signature against Google's published public keys;
  - verifies the token has not expired;
  - verifies the `aud` (audience) claim matches our configured client ID.

Isolated in its own module specifically so tests can substitute this one
function and make zero real Google network calls.
"""

from __future__ import annotations

from dataclasses import dataclass

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.exceptions import InvalidGoogleCredentialError


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str
    full_name: str
    avatar_url: str | None


def verify_google_credential(credential: str, client_id: str) -> GoogleIdentity:
    """Verify a Google ID token and return the verified identity claims.

    Raises InvalidGoogleCredentialError for any verification failure
    (bad signature, expired, wrong audience, unverified email, or a missing
    required claim) — deliberately one error type, since the frontend must
    never learn which specific check failed (that's provider-internal
    detail, not something to leak to a client).
    """
    try:
        claims = google_id_token.verify_oauth2_token(credential, google_requests.Request(), client_id)
    except Exception as exc:  # noqa: BLE001 - google-auth raises several exception types here
        raise InvalidGoogleCredentialError("Google credential verification failed.") from exc

    if not claims.get("email_verified"):
        raise InvalidGoogleCredentialError("Google account email is not verified.")

    subject = claims.get("sub")
    email = claims.get("email")
    if not subject or not email:
        raise InvalidGoogleCredentialError("Google credential is missing required identity claims.")

    return GoogleIdentity(
        subject=subject,
        email=email,
        full_name=claims.get("name") or email,
        avatar_url=claims.get("picture"),
    )
