"""Auth HTTP boundary. No password/session logic lives here — everything
delegates to app.auth.service, matching the rest of TradeLens's
route/service separation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.auth.schemas import (
    GoogleAuthRequest,
    LoginRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    UserResponse,
)
from app.core.config import settings
from app.core.exceptions import InvalidGoogleCredentialError
from app.db import get_db_session

router = APIRouter()


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.is_production,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    # Attributes must match what the cookie was originally set with --
    # browsers are strict about SameSite=None requiring Secure, so an
    # unmatched default (secure=False, samesite="lax") can fail to clear
    # a production ("none"/Secure) cookie correctly.
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.is_production,
        samesite=settings.session_cookie_samesite,
    )


@router.post("/auth/register", response_model=UserResponse, status_code=201, summary="Register a local account")
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db_session)) -> UserResponse:
    user = service.register_local(
        db,
        full_name=payload.full_name,
        display_name=payload.display_name,
        email=payload.email,
        password=payload.password,
    )
    token = service.create_session(db, user, ttl_days=settings.session_ttl_days)
    _set_session_cookie(response, token)
    return UserResponse.from_domain(user)


@router.post("/auth/login", response_model=UserResponse, summary="Log in with email and password")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db_session)) -> UserResponse:
    user = service.authenticate_local(db, email=payload.email, password=payload.password)
    token = service.create_session(db, user, ttl_days=settings.session_ttl_days)
    _set_session_cookie(response, token)
    return UserResponse.from_domain(user)


@router.post("/auth/google", response_model=UserResponse, summary="Sign in with a verified Google credential")
def google_login(
    payload: GoogleAuthRequest, response: Response, db: Session = Depends(get_db_session)
) -> UserResponse:
    if not settings.google_client_id:
        raise InvalidGoogleCredentialError("Google sign-in is not configured on this server.")
    user = service.authenticate_google(db, credential=payload.credential, client_id=settings.google_client_id)
    token = service.create_session(db, user, ttl_days=settings.session_ttl_days)
    _set_session_cookie(response, token)
    return UserResponse.from_domain(user)


@router.post("/auth/logout", status_code=204, response_model=None, summary="Revoke the current session")
def logout(request: Request, response: Response, db: Session = Depends(get_db_session)) -> None:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token:
        service.revoke_session(db, raw_token)
    _clear_session_cookie(response)


@router.get("/auth/me", response_model=UserResponse, summary="Current authenticated user")
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.from_domain(current_user)


@router.patch("/auth/me", response_model=UserResponse, summary="Update editable profile fields")
def update_me(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> UserResponse:
    updated = service.update_profile(
        db, current_user, full_name=payload.full_name, display_name=payload.display_name
    )
    return UserResponse.from_domain(updated)
