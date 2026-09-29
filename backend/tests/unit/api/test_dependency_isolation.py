def test_request_failure_does_not_contaminate_subsequent_request(client):
    failing = client.get("/api/v1/instruments/NOTREAL")
    assert failing.status_code == 404

    normal = client.get("/api/v1/instruments/RELIANCE")
    assert normal.status_code == 200
    assert normal.json()["symbol"] == "RELIANCE"
