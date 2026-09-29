def test_strategy_identity(client):
    response = client.get(
        "/api/v1/strategies/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-01-10", "interval": "1d"},
    )
    body = response.json()
    assert body["strategy_id"] == "trend_momentum_v1"
    assert body["strategy_name"] == "Trend + Momentum v1"
    assert all(e["strategy_id"] == "trend_momentum_v1" for e in body["evaluations"])
    assert all(e["strategy_name"] == "Trend + Momentum v1" for e in body["evaluations"])


def test_chronology_preserved(client):
    response = client.get(
        "/api/v1/strategies/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-01-15", "interval": "1d"},
    )
    dates = [e["date"] for e in response.json()["evaluations"]]
    assert dates == sorted(dates)


def test_warm_up_row_is_insufficient_data_with_no_partial_conditions(client):
    response = client.get(
        "/api/v1/strategies/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-01-05", "interval": "1d"},
    )
    first = response.json()["evaluations"][0]
    assert first["decision"] == "INSUFFICIENT_DATA"
    assert first["conditions"] == []
    assert first["missing_inputs"] != []


def test_insufficient_data_serializes_exactly(client):
    response = client.get(
        "/api/v1/strategies/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-01-05", "interval": "1d"},
    )
    first = response.json()["evaluations"][0]
    assert first["decision"] == "INSUFFICIENT_DATA"
    assert first["conditions"] == []
    assert isinstance(first["missing_inputs"], list)
    assert set(first["missing_inputs"]).issubset({"close", "sma20", "sma50", "rsi14"})


def test_sufficient_row_has_exactly_three_conditions_in_stable_order(client):
    # request through day 90 covers well past all warm-up periods (SMA50=50, RSI=15, volume=21)
    response = client.get(
        "/api/v1/strategies/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    evaluations = response.json()["evaluations"]
    sufficient = [e for e in evaluations if e["decision"] != "INSUFFICIENT_DATA"]
    assert len(sufficient) > 0
    for evaluation in sufficient:
        assert len(evaluation["conditions"]) == 3
        assert [c["condition_id"] for c in evaluation["conditions"]] == [
            "close_above_sma20", "sma20_above_sma50", "rsi_in_range",
        ]
        for condition in evaluation["conditions"]:
            for value in condition["actual_values"] + condition["reference_values"]:
                assert isinstance(value["value"], (int, float))


def test_at_least_one_buy_and_one_no_signal_present(client):
    response = client.get(
        "/api/v1/strategies/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    decisions = {e["decision"] for e in response.json()["evaluations"]}
    assert "BUY" in decisions
    assert "NO_SIGNAL" in decisions
    assert "INSUFFICIENT_DATA" in decisions


def test_strategy_single_market_fetch(client, fake_market_data_service):
    client.get(
        "/api/v1/strategies/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-02-01", "interval": "1d"},
    )
    assert len(fake_market_data_service.calls) == 1


def test_repeated_identical_request_is_deterministic(client):
    params = {"start": "2024-01-01", "end": "2024-02-01", "interval": "1d"}
    r1 = client.get("/api/v1/strategies/trend-momentum-v1/RELIANCE", params=params)
    r2 = client.get("/api/v1/strategies/trend-momentum-v1/RELIANCE", params=params)
    assert r1.json() == r2.json()
