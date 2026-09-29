"""Phase 4E manual acceptance helper (not a test -- run manually).

Uses FastAPI's TestClient with a deterministic fake `MarketDataService`
(no network) to exercise the real HTTP endpoint
`GET /api/v1/investigations/trend-momentum-v1/{symbol}`, prints the
response, and independently cross-checks it against a direct
2A -> 4A -> 4B -> 4C -> 4D domain pipeline built from the SAME fixture --
the API must be a serialization boundary, not another calculation
boundary.

No network. Run with:

    cd backend
    PYTHONPATH=. python scripts/phase4e_manual_verification.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import app.api.routes.investigations as investigations_route
from app.api.dependencies import get_market_data_service
from app.indicators.engine import compute_indicators
from app.investigation.comparison import build_failure_population_comparison
from app.investigation.composer import build_strategy_failure_investigation
from app.investigation.context import build_failure_context_dataset
from app.investigation.engine import build_signal_investigation_dataset
from app.main import app
from app.market_data.models import OHLCVBar, OHLCVSeries
from app.outcomes.engine import compute_signal_outcomes
from app.strategies.engine import evaluate_strategy

SYMBOL = "RELIANCE"


def _make_repeating_cycle_series(n_cycles: int, cycle_len: int = 90, start: date = date(2024, 1, 1)) -> OHLCVSeries:
    def _cycle_closes() -> list[float]:
        closes, close = [], 100.0
        for i in range(cycle_len):
            if i < 50:
                close += 0.01
            elif i < 65:
                close += 3.0
            else:
                close -= 3.0
            closes.append(close)
        return closes

    all_closes = _cycle_closes() * n_cycles
    bars = tuple(
        OHLCVBar(date=start + timedelta(days=i), open=c, high=c + 2, low=c - 2, close=c, adj_close=c, volume=1000)
        for i, c in enumerate(all_closes)
    )
    return OHLCVSeries(provider_symbol="RELIANCE.NS", interval="1d", bars=bars)


class _FakeMarketDataService:
    def __init__(self, series: OHLCVSeries):
        self._series = series
        self.calls = 0

    def get_history(self, symbol, interval, start_date, end_date, today=None):
        self.calls += 1
        return self._series.sliced(start_date, end_date)


def _fmt(value) -> str:
    return "n/a" if value is None else (f"{value:+.6f}" if isinstance(value, float) else str(value))


def main() -> None:
    series = _make_repeating_cycle_series(n_cycles=3)
    # start=bars[150], end=bars[255]: puts the fixture's last BUY cluster
    # (idx 248-249) within 10 forward bars of `end` -> a genuine
    # near-end censored (UNAVAILABLE) BUY signal is included.
    start = series.bars[150].date
    end = series.bars[255].date

    fake = _FakeMarketDataService(series)
    app.dependency_overrides[get_market_data_service] = lambda: fake
    client = TestClient(app)

    print("PHASE 4E FASTAPI VERIFICATION")
    print()
    print("REQUEST")
    print(f"  endpoint: /api/v1/investigations/trend-momentum-v1/{SYMBOL}")
    print(f"  start:    {start.isoformat()}")
    print(f"  end:      {end.isoformat()}")
    print("  interval: 1d")
    print()

    response = client.get(
        f"/api/v1/investigations/trend-momentum-v1/{SYMBOL}", params={"start": start.isoformat(), "end": end.isoformat(), "interval": "1d"}
    )
    print("RESPONSE")
    print(f"  status: {response.status_code}")
    print()

    body = response.json()

    print("METADATA")
    print(f"  symbol: {body['provider_symbol']}  interval: {body['interval']}  strategy: {body['strategy_id']}")
    print()

    print("POPULATION")
    print(
        f"  total={body['total_signal_count']} eligible={body['eligible_count']} failed={body['failed_count']} "
        f"non_failed={body['non_failed_count']} unavailable={body['unavailable_count']}"
    )
    print()

    print("OUTCOME COMPARISON")
    for label in ("failed", "non_failed"):
        s = body["outcome_comparison"][label]
        print(f"  {label}: count={s['count']} avg_return={_fmt(s['average_forward_return_10d'])} worst_mae={_fmt(s['worst_mae_10d'])} best_mfe={_fmt(s['best_mfe_10d'])}")
    print()

    print("SIGNAL-TIME CONTEXT COMPARISON")
    for label in ("failed", "non_failed"):
        s = body["context_analysis"][label]
        print(f"  {label}: count={s['count']} avg_rsi={_fmt(s['average_rsi14'])} avg_vol={_fmt(s['average_annualized_realized_volatility_20'])}")
    print()

    print("OBSERVATIONS (first 5)")
    for o in body["context_analysis"]["observations"][:5]:
        print(f"  {o['signal_date']}  {o['classification']:<12} {o['regime']:<15} RSI={_fmt(o['rsi14'])} vol={_fmt(o['annualized_realized_volatility_20'])}")
    print()

    # --- Independent domain cross-check ---------------------------------
    calc_start = start - timedelta(days=investigations_route.CALCULATION_WARMUP_CALENDAR_DAYS)
    market_series = series.sliced(calc_start, end)
    indicator_series = compute_indicators(market_series)
    evaluation_series = evaluate_strategy(market_series, indicator_series)
    outcome_series = compute_signal_outcomes(market_series, evaluation_series)
    windowed = investigations_route._restrict_to_window(outcome_series, start, end)
    dataset = build_signal_investigation_dataset(windowed)
    comparison = build_failure_population_comparison(dataset)
    context = build_failure_context_dataset(dataset, market_series, indicator_series)
    domain = build_strategy_failure_investigation(dataset, comparison, context)

    assert response.status_code == 200
    print("Status is 200.")

    assert body["provider_symbol"] == domain.provider_symbol
    assert body["interval"] == domain.interval
    assert body["strategy_id"] == domain.strategy_id
    assert body["strategy_name"] == domain.strategy_name
    print("Metadata matches the direct domain pipeline exactly.")

    assert body["total_signal_count"] == domain.total_signal_count
    assert body["eligible_count"] == domain.eligible_count
    assert body["failed_count"] == domain.failed_count
    assert body["non_failed_count"] == domain.non_failed_count
    assert body["unavailable_count"] == domain.unavailable_count
    print("Population counts match exactly.")

    assert body["outcome_comparison"]["failed"]["average_forward_return_10d"] == domain.outcome_comparison.failed.average_forward_return_10d
    assert body["outcome_comparison"]["non_failed"]["worst_mae_10d"] == domain.outcome_comparison.non_failed.worst_mae_10d
    print("Outcome comparison values match exactly.")

    assert body["context_analysis"]["failed"]["average_rsi14"] == domain.context_analysis.failed.average_rsi14
    assert body["context_analysis"]["non_failed"]["average_close_above_sma20_fraction"] == domain.context_analysis.non_failed.average_close_above_sma20_fraction
    print("Context comparison values match exactly.")

    assert len(body["context_analysis"]["observations"]) == len(domain.context_analysis.observations)
    for api_obs, domain_obs in zip(body["context_analysis"]["observations"], domain.context_analysis.observations):
        assert api_obs["signal_date"] == domain_obs.signal_date.isoformat()
        assert api_obs["classification"] == domain_obs.classification.value
        assert api_obs["regime"] == domain_obs.regime.value
    print("Observation sequence, classification strings, and regime strings match exactly.")

    # Null / decimal / sign checks.
    for o in body["context_analysis"]["observations"]:
        assert o["annualized_realized_volatility_20"] is None or abs(o["annualized_realized_volatility_20"]) < 1
        assert abs(o["close_above_sma20_fraction"]) < 1
        assert abs(o["sma20_above_sma50_fraction"]) < 1
    for label in ("failed", "non_failed"):
        s = body["outcome_comparison"][label]
        if s["worst_mae_10d"] is not None:
            assert s["worst_mae_10d"] <= 0
    print("Fractions stay decimal (never *100); MAE stays signed; null stays null.")

    # Near-end censored BUY explicitly present.
    unavailable = [o for o in body["context_analysis"]["observations"] if o["classification"] == "UNAVAILABLE"]
    assert unavailable, "expected at least one near-end UNAVAILABLE observation in this fixture"
    for o in unavailable:
        assert o["signal_date"] in {b.date.isoformat() for b in series.bars[240:256]}
    print(f"Near-end censored BUY signal(s) present and retained: {[o['signal_date'] for o in unavailable]}")

    assert fake.calls == 1
    print("Market data fetched exactly once for this request.")

    print()
    print("ALL MANUAL PHASE 4E CHECKS PASSED")


if __name__ == "__main__":
    main()
