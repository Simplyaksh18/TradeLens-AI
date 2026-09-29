import pytest


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_allowed_origin_preflight(client, origin):
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == origin


def test_disallowed_origin_preflight_does_not_grant_access(client):
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Starlette's CORS middleware does not crash for a disallowed origin; it
    # simply omits the Allow-Origin header for that origin.
    assert response.headers.get("access-control-allow-origin") != "http://evil.example.com"


def test_ordinary_request_without_origin_header_behaves_normally(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
