def test_market_data_indicators_strategy_agree_on_identity_and_length(client):
    params = {"start": "2024-01-01", "end": "2024-02-15", "interval": "1d"}

    market = client.get("/api/v1/market-data/RELIANCE", params=params).json()
    indicators = client.get("/api/v1/indicators/RELIANCE", params=params).json()
    strategy = client.get("/api/v1/strategies/trend-momentum-v1/RELIANCE", params=params).json()

    assert market["provider_symbol"] == indicators["provider_symbol"] == strategy["provider_symbol"]
    assert market["interval"] == indicators["interval"] == strategy["interval"]

    market_dates = [b["date"] for b in market["bars"]]
    indicator_dates = [r["date"] for r in indicators["rows"]]
    strategy_dates = [e["date"] for e in strategy["evaluations"]]
    assert market_dates == indicator_dates == strategy_dates

    assert len(market["bars"]) == len(indicators["rows"]) == len(strategy["evaluations"])
