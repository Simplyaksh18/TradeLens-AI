def test_search_case_insensitive_deterministic(client):
    response = client.get("/api/v1/instruments", params={"q": "rel"})
    assert response.status_code == 200
    body = response.json()
    symbols = [r["symbol"] for r in body["results"]]
    assert symbols == ["RELIANCE"]
    assert body["results"][0]["provider_symbol"] == "RELIANCE.NS"


def test_search_matches_company_name(client):
    response = client.get("/api/v1/instruments", params={"q": "infosys"})
    assert response.status_code == 200
    assert [r["symbol"] for r in response.json()["results"]] == ["INFY"]


def test_search_bounded_result_count(client):
    response = client.get("/api/v1/instruments", params={"q": "e", "limit": 1})
    assert response.status_code == 200
    assert len(response.json()["results"]) <= 1


def test_search_invalid_limit_zero_rejected(client):
    response = client.get("/api/v1/instruments", params={"q": "rel", "limit": 0})
    assert response.status_code == 422


def test_search_invalid_limit_too_large_rejected(client):
    response = client.get("/api/v1/instruments", params={"q": "rel", "limit": 101})
    assert response.status_code == 422


def test_search_no_provider_call(client, fake_market_data_service):
    client.get("/api/v1/instruments", params={"q": "rel"})
    assert fake_market_data_service.calls == []


def test_lookup_known_instrument(client):
    response = client.get("/api/v1/instruments/RELIANCE")
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "RELIANCE"
    assert body["provider_symbol"] == "RELIANCE.NS"
    assert body["exchange"] == "NSE"
    assert body["instrument_type"] == "EQUITY"


def test_lookup_unknown_instrument_returns_structured_404(client):
    response = client.get("/api/v1/instruments/NOTREAL")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "INSTRUMENT_NOT_FOUND"
    assert "traceback" not in str(body).lower()
