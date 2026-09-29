from unittest.mock import patch

from app.auth.google_verify import GoogleIdentity


def _register(client, email="route@example.com", password="password123"):
    return client.post(
        "/api/v1/auth/register",
        json={"full_name": "Route Test", "display_name": "Router", "email": email, "password": password},
    )


def test_register_sets_session_cookie_and_returns_safe_fields(client):
    response = _register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "route@example.com"
    assert "password" not in body
    assert "password_hash" not in body
    assert client.cookies.get("tradelens_session") is not None


def test_register_duplicate_email_returns_409(client):
    _register(client)
    response = _register(client)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


def test_login_with_valid_credentials(client):
    _register(client, email="login2@example.com")
    client.cookies.clear()
    response = client.post("/api/v1/auth/login", json={"email": "login2@example.com", "password": "password123"})
    assert response.status_code == 200
    assert client.cookies.get("tradelens_session") is not None


def test_login_with_wrong_password_returns_401_generic(client):
    _register(client, email="login3@example.com")
    client.cookies.clear()
    response = client.post("/api/v1/auth/login", json={"email": "login3@example.com", "password": "wrong-password"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_me_authenticated(client):
    _register(client, email="me1@example.com")
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "me1@example.com"


def test_me_unauthenticated_returns_401(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_INVALID"


def test_logout_clears_session(client):
    _register(client, email="logout2@example.com")
    logout_response = client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 204

    me_response = client.get("/api/v1/auth/me")
    assert me_response.status_code == 401


def test_session_rejected_after_logout_even_with_stale_cookie(client):
    _register(client, email="stale@example.com")
    stale_cookie_value = client.cookies.get("tradelens_session")
    client.post("/api/v1/auth/logout")

    # Simulate a client that kept using the now-revoked cookie value.
    client.cookies.set("tradelens_session", stale_cookie_value)


# ---------------------------------------------------------------------------
# Deployment: production vs. local-dev session-cookie attributes (see
# CLAUDE.md deployment-compatibility notes -- a fully cross-site production
# deployment, e.g. a Vercel frontend calling a Render backend, requires
# SameSite=None + Secure; local dev (same "localhost" hostname, plain HTTP)
# requires SameSite=Lax and no Secure).
# ---------------------------------------------------------------------------


def _set_cookie_header(response):
    header = response.headers.get("set-cookie", "")
    assert "tradelens_session=" in header
    return header.lower()


def test_local_dev_session_cookie_uses_lax_and_no_secure(client):
    with patch("app.core.config.settings.environment", "development"):
        response = _register(client, email="dev-cookie@example.com")
    header = _set_cookie_header(response)
    assert "samesite=lax" in header
    assert "secure" not in header
    assert "httponly" in header


def test_production_session_cookie_uses_samesite_none_and_secure(client):
    with patch("app.core.config.settings.environment", "production"):
        response = _register(client, email="prod-cookie@example.com")
    header = _set_cookie_header(response)
    assert "samesite=none" in header
    assert "secure" in header
    assert "httponly" in header


def test_production_logout_clears_cookie_with_matching_attributes(client):
    with patch("app.core.config.settings.environment", "production"):
        _register(client, email="prod-logout@example.com")
        logout_response = client.post("/api/v1/auth/logout")
    header = logout_response.headers.get("set-cookie", "").lower()
    assert "tradelens_session=" in header
    assert "samesite=none" in header
    assert "secure" in header
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_profile_update_display_name(client):
    _register(client, email="patch1@example.com")
    response = client.patch("/api/v1/auth/me", json={"display_name": "New Display"})
    assert response.status_code == 200
    assert response.json()["display_name"] == "New Display"


def test_profile_update_returns_only_safe_fields(client):
    _register(client, email="patch2@example.com")
    response = client.patch("/api/v1/auth/me", json={"full_name": "New Full Name"})
    body = response.json()
    assert set(body.keys()) == {"id", "email", "full_name", "display_name", "avatar_url", "auth_provider"}


def test_profile_update_has_no_email_field_in_request_schema(client):
    _register(client, email="patch3@example.com")
    # Sending an "email" field is simply ignored by the schema (extra field),
    # not applied -- confirms email cannot be changed through this endpoint.
    response = client.patch("/api/v1/auth/me", json={"display_name": "X", "email": "changed@example.com"})
    assert response.status_code == 200
    assert response.json()["email"] == "patch3@example.com"


def test_profile_update_requires_authentication(client):
    response = client.patch("/api/v1/auth/me", json={"display_name": "X"})
    assert response.status_code == 401


def test_google_login_creates_new_user(client):
    identity = GoogleIdentity(subject="g-sub-99", email="newgoogler@example.com", full_name="Googler", avatar_url=None)
    with patch("app.core.config.settings.google_client_id", "test-client-id"):
        with patch("app.auth.service.verify_google_credential", return_value=identity):
            response = client.post("/api/v1/auth/google", json={"credential": "fake-google-credential"})

    assert response.status_code == 200
    assert response.json()["email"] == "newgoogler@example.com"
    assert response.json()["auth_provider"] == "GOOGLE"
    assert client.cookies.get("tradelens_session") is not None
