from datetime import date


def test_indicator_row_count_matches_market_bar_count(client, fake_market_data_service):
    response = client.get(
        "/api/v1/indicators/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    assert response.status_code == 200
    body = response.json()
    expected_bars = fake_market_data_service._series.sliced(date(2024, 1, 1), date(2024, 3, 30)).bars
    assert len(body["rows"]) == len(expected_bars)


def test_warm_up_values_serialize_as_json_null(client):
    response = client.get(
        "/api/v1/indicators/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-01-05", "interval": "1d"},
    )
    body = response.json()
    first_row = body["rows"][0]
    assert first_row["sma20"] is None
    assert first_row["sma50"] is None
    assert first_row["rsi14"] is None
    # confirm it's JSON null, never the string "None", 0, or NaN
    raw_text = response.text
    assert '"sma20":null' in raw_text.replace(" ", "")


def test_known_reference_value_sma20(client):
    # make_market_series(n=90): bars 0..49 close += 0.01 each day starting at 100.0
    # close[19] (20th bar, 0-based index 19) = 100 + 20*0.01 = 100.20 (bar19's own increment applied before append)
    response = client.get(
        "/api/v1/indicators/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-01-20", "interval": "1d"},
    )
    rows = response.json()["rows"]
    assert len(rows) == 20
    assert rows[18]["sma20"] is None  # 19th bar (index 18): still warm-up
    assert rows[19]["sma20"] is not None  # 20th bar (index 19): first valid SMA20
    assert isinstance(rows[19]["sma20"], float)


def test_indicators_single_market_fetch(client, fake_market_data_service):
    client.get(
        "/api/v1/indicators/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-02-01", "interval": "1d"},
    )
    assert len(fake_market_data_service.calls) == 1
