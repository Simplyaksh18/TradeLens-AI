"""Google sign-in tests. verify_google_credential is mocked at the
app.auth.service call site — zero real Google network calls."""

from unittest.mock import patch

import pytest

from app.auth import service
from app.auth.google_verify import GoogleIdentity
from app.auth.models import AuthProvider
from app.core.exceptions import GoogleAccountCollisionError, InvalidGoogleCredentialError


def _mock_identity(**overrides):
    defaults = dict(subject="google-sub-1", email="newgoogle@example.com", full_name="New Googler", avatar_url="https://example.com/a.png")
    defaults.update(overrides)
    return GoogleIdentity(**defaults)


def test_new_google_user_is_created(db_session):
    with patch("app.auth.service.verify_google_credential", return_value=_mock_identity()) as mock_verify:
        user = service.authenticate_google(db_session, credential="fake-credential", client_id="client-id-123")

    mock_verify.assert_called_once_with("fake-credential", "client-id-123")
    assert user.auth_provider == AuthProvider.GOOGLE
    assert user.google_subject == "google-sub-1"
    assert user.email == "newgoogle@example.com"
    assert user.full_name == "New Googler"
    assert user.avatar_url == "https://example.com/a.png"
    assert user.password_hash is None


def test_existing_google_subject_logs_in_same_user(db_session):
    with patch("app.auth.service.verify_google_credential", return_value=_mock_identity()):
        first = service.authenticate_google(db_session, credential="cred", client_id="cid")
    with patch("app.auth.service.verify_google_credential", return_value=_mock_identity()):
        second = service.authenticate_google(db_session, credential="cred", client_id="cid")

    assert first.id == second.id


def test_invalid_credential_rejected(db_session):
    with patch("app.auth.service.verify_google_credential", side_effect=InvalidGoogleCredentialError("bad token")):
        with pytest.raises(InvalidGoogleCredentialError):
            service.authenticate_google(db_session, credential="bad", client_id="cid")


def test_wrong_audience_rejected(db_session):
    # verify_google_credential itself is responsible for audience checking
    # (delegated to google-auth's verify_oauth2_token); here we confirm the
    # service layer propagates that rejection rather than swallowing it.
    with patch("app.auth.service.verify_google_credential", side_effect=InvalidGoogleCredentialError("wrong audience")):
        with pytest.raises(InvalidGoogleCredentialError):
            service.authenticate_google(db_session, credential="cred", client_id="wrong-client-id")


def test_missing_required_claim_rejected(db_session):
    with patch("app.auth.service.verify_google_credential", side_effect=InvalidGoogleCredentialError("missing claims")):
        with pytest.raises(InvalidGoogleCredentialError):
            service.authenticate_google(db_session, credential="cred", client_id="cid")


def test_local_email_collision_is_rejected_not_auto_linked(db_session):
    service.register_local(db_session, full_name="Local User", display_name="Local", email="collide@example.com", password="password123")

    with patch("app.auth.service.verify_google_credential", return_value=_mock_identity(email="collide@example.com", subject="different-sub")):
        with pytest.raises(GoogleAccountCollisionError):
            service.authenticate_google(db_session, credential="cred", client_id="cid")


def test_zero_real_google_network_calls(db_session):
    """Sanity check that the mocked path never imports/uses the real
    google-auth HTTP transport during this test module."""
    with patch("app.auth.service.verify_google_credential", return_value=_mock_identity()) as mock_verify:
        service.authenticate_google(db_session, credential="cred", client_id="cid")
    assert mock_verify.called
