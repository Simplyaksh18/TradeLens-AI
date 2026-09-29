from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.service import get_user_for_session
from app.core.config import settings
from app.core.exceptions import SessionInvalidError
from app.db import get_db_session


def get_current_user(request: Request, db: Session = Depends(get_db_session)) -> User:
    """Resolve the authenticated user from the session cookie.

    Raises SessionInvalidError (mapped to 401) when the cookie is missing,
    unknown, expired, or revoked — never distinguishes which case to the
    caller, same account-enumeration-avoidance rationale as login.
    """
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise SessionInvalidError()
    return get_user_for_session(db, raw_token)
