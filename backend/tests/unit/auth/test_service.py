import pytest

from app.auth import service
from app.auth.models import AuthProvider
from app.core.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    SessionInvalidError,
    WeakPasswordError,
)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_valid_registration(db_session):
    user = service.register_local(
        db_session, full_name="Akshi Kumar", display_name="Akshi", email="Akshi@Example.com", password="a-long-enough-pw"
    )
    assert user.email == "akshi@example.com"  # normalized: trimmed + lowercased
    assert user.auth_provider == AuthProvider.LOCAL
    assert user.password_hash is not None
    assert user.password_hash != "a-long-enough-pw"  # never stored in plaintext


def test_duplicate_email_rejected(db_session):
    service.register_local(db_session, full_name="A", display_name="A", email="dup@example.com", password="password123")
    with pytest.raises(EmailAlreadyRegisteredError):
        service.register_local(db_session, full_name="B", display_name="B", email="DUP@example.com ", password="password123")


def test_weak_password_rejected(db_session):
    with pytest.raises(WeakPasswordError):
        service.register_local(db_session, full_name="A", display_name="A", email="short@example.com", password="short")


def test_password_hash_never_returned_as_plaintext(db_session):
    user = service.register_local(
        db_session, full_name="A", display_name="A", email="hash@example.com", password="password123"
    )
    from app.auth.schemas import UserResponse

    response = UserResponse.from_domain(user)
    assert "password" not in response.model_dump()
    assert "password_hash" not in response.model_dump()


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def test_valid_login(db_session):
    service.register_local(db_session, full_name="A", display_name="A", email="login@example.com", password="password123")
    user = service.authenticate_local(db_session, email="login@example.com", password="password123")
    assert user.email == "login@example.com"


def test_wrong_password_rejected(db_session):
    service.register_local(db_session, full_name="A", display_name="A", email="wrong@example.com", password="password123")
    with pytest.raises(InvalidCredentialsError):
        service.authenticate_local(db_session, email="wrong@example.com", password="not-the-password")


def test_unknown_email_rejected(db_session):
    with pytest.raises(InvalidCredentialsError):
        service.authenticate_local(db_session, email="nobody@example.com", password="password123")


def test_inactive_user_rejected(db_session):
    user = service.register_local(
        db_session, full_name="A", display_name="A", email="inactive@example.com", password="password123"
    )
    user.is_active = False
    db_session.commit()
    with pytest.raises(InvalidCredentialsError):
        service.authenticate_local(db_session, email="inactive@example.com", password="password123")


def test_google_only_user_cannot_login_locally(db_session):
    from app.auth.models import User

    google_user = User(
        email="googleonly@example.com", full_name="G", display_name="G",
        auth_provider=AuthProvider.GOOGLE, google_subject="sub-123", password_hash=None,
    )
    db_session.add(google_user)
    db_session.commit()

    with pytest.raises(InvalidCredentialsError):
        service.authenticate_local(db_session, email="googleonly@example.com", password="anything")


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def test_authenticated_session_resolves_user(db_session):
    user = service.register_local(db_session, full_name="A", display_name="A", email="sess@example.com", password="password123")
    token = service.create_session(db_session, user, ttl_days=14)
    resolved = service.get_user_for_session(db_session, token)
    assert resolved.id == user.id


def test_unknown_session_token_rejected(db_session):
    with pytest.raises(SessionInvalidError):
        service.get_user_for_session(db_session, "not-a-real-token")


def test_logout_revokes_session(db_session):
    user = service.register_local(db_session, full_name="A", display_name="A", email="logout@example.com", password="password123")
    token = service.create_session(db_session, user, ttl_days=14)
    service.revoke_session(db_session, token)
    with pytest.raises(SessionInvalidError):
        service.get_user_for_session(db_session, token)


def test_expired_session_rejected(db_session):
    from datetime import datetime, timedelta, timezone
    from app.auth.models import UserSession
    from app.auth.security import generate_session_token, hash_session_token

    user = service.register_local(db_session, full_name="A", display_name="A", email="expired@example.com", password="password123")
    raw_token = generate_session_token()
    expired_session = UserSession(
        token_hash=hash_session_token(raw_token),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add(expired_session)
    db_session.commit()

    with pytest.raises(SessionInvalidError):
        service.get_user_for_session(db_session, raw_token)


# ---------------------------------------------------------------------------
# Profile update
# ---------------------------------------------------------------------------


def test_update_display_name(db_session):
    user = service.register_local(db_session, full_name="A", display_name="Old", email="profile1@example.com", password="password123")
    updated = service.update_profile(db_session, user, full_name=None, display_name="New")
    assert updated.display_name == "New"
    assert updated.full_name == "A"


def test_update_full_name(db_session):
    user = service.register_local(db_session, full_name="Old Name", display_name="D", email="profile2@example.com", password="password123")
    updated = service.update_profile(db_session, user, full_name="New Name", display_name=None)
    assert updated.full_name == "New Name"


def test_profile_update_cannot_change_email(db_session):
    user = service.register_local(db_session, full_name="A", display_name="D", email="fixed@example.com", password="password123")
    # update_profile has no email parameter at all -- structurally cannot change it
    import inspect
    assert "email" not in inspect.signature(service.update_profile).parameters
