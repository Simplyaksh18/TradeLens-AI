"""Phase 3D: /audits route tests (Phase 3C exposed through the API)."""

import math
from datetime import date, timedelta

from app.api.dependencies import get_market_data_service
from app.audit.engine import build_strategy_audit
from app.core.exceptions import InstrumentNotFoundError
from app.indicators.engine import compute_indicators
from app.main import app
from app.market_data.models import OHLCVBar, OHLCVSeries
from app.outcomes.engine import compute_signal_outcomes
from app.strategies.engine import evaluate_strategy
from tests.unit.api.conftest import FakeMarketDataService, make_market_series


def _find_date_for_decision(client, decision: str) -> str:
    response = client.get(
        "/api/v1/strategies/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    for e in response.json()["evaluations"]:
        if e["decision"] == decision:
            return e["date"]
    raise AssertionError(f"No {decision} evaluation found in fixture range")


def test_buy_audit_200_and_full_composition(client):
    audit_date = _find_date_for_decision(client, "BUY")
    response = client.get(
        "/api/v1/audits/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d", "audit_date": audit_date},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["evaluation"]["decision"] == "BUY"
    assert body["audit_date"] == audit_date
    assert body["retrospective_outcome"] is not None


def test_no_signal_audit_200_retrospective_null(client):
    audit_date = _find_date_for_decision(client, "NO_SIGNAL")
    response = client.get(
        "/api/v1/audits/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d", "audit_date": audit_date},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["evaluation"]["decision"] == "NO_SIGNAL"
    assert body["retrospective_outcome"] is None


def test_insufficient_data_audit_is_200_not_error(client):
    audit_date = _find_date_for_decision(client, "INSUFFICIENT_DATA")
    response = client.get(
        "/api/v1/audits/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d", "audit_date": audit_date},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["evaluation"]["decision"] == "INSUFFICIENT_DATA"
    assert body["retrospective_outcome"] is None
    assert body["historical_evidence"]["prior_signal_count"] == 0


def test_exact_requested_audit_date_preserved(client):
    audit_date = _find_date_for_decision(client, "BUY")
    response = client.get(
        "/api/v1/audits/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d", "audit_date": audit_date},
    )
    assert response.json()["audit_date"] == audit_date


def test_historical_evidence_serialization(client):
    audit_date = _find_date_for_decision(client, "BUY")
    response = client.get(
        "/api/v1/audits/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d", "audit_date": audit_date},
    )
    hist = response.json()["historical_evidence"]
    assert set(hist.keys()) == {"prior_signal_count", "five_bar", "ten_bar"}
    for horizon in ("five_bar", "ten_bar"):
        assert set(hist[horizon].keys()) == {
            "eligible_outcome_count", "positive_count", "negative_count", "breakeven_count", "hit_rate", "average_return",
        }


def test_historical_signal_risk_serialization(client):
    audit_date = _find_date_for_decision(client, "BUY")
    response = client.get(
        "/api/v1/audits/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d", "audit_date": audit_date},
    )
    risk = response.json()["historical_signal_risk"]
    assert set(risk.keys()) == {"eligible_outcome_count", "average_mae_10d", "worst_mae_10d", "average_mfe_10d", "best_mfe_10d"}


def test_risk_market_context_serialization(client):
    audit_date = _find_date_for_decision(client, "BUY")
    response = client.get(
        "/api/v1/audits/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d", "audit_date": audit_date},
    )
    ctx = response.json()["risk_market_context"]
    assert set(ctx.keys()) == {"annualized_realized_volatility_20", "regime", "regime_evidence"}
    assert set(ctx["regime_evidence"].keys()) == {"close", "sma20", "sma50", "close_vs_sma20", "sma20_vs_sma50"}
    assert ctx["regime"] in {"BULLISH_TREND", "BEARISH_TREND", "TRANSITIONAL", "INSUFFICIENT_DATA"}


def test_retrospective_outcome_serialization_and_reference_close_terminology(client):
    audit_date = _find_date_for_decision(client, "BUY")
    response = client.get(
        "/api/v1/audits/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d", "audit_date": audit_date},
    )
    retro = response.json()["retrospective_outcome"]
    assert set(retro.keys()) == {
        "date", "decision", "reference_close", "forward_close_5d", "forward_return_5d",
        "forward_close_10d", "forward_return_10d", "mae_10d", "mfe_10d", "available_forward_bars",
    }


def test_population_invariant_5bar_ge_10bar_and_risk_matches_ten_bar(client):
    audit_date = _find_date_for_decision(client, "BUY")
    response = client.get(
        "/api/v1/audits/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d", "audit_date": audit_date},
    )
    body = response.json()
    hist = body["historical_evidence"]
    assert hist["prior_signal_count"] >= hist["five_bar"]["eligible_outcome_count"] >= hist["ten_bar"]["eligible_outcome_count"]
    assert body["historical_signal_risk"]["eligible_outcome_count"] == hist["ten_bar"]["eligible_outcome_count"]


def test_response_matches_direct_domain_computation(client, fake_market_data_service):
    """Cross-layer invariant: the API response must equal the same fields
    computed directly from the domain layer for the identical input."""
    market_series = fake_market_data_service._series
    indicator_series = compute_indicators(market_series)
    evaluation_series = evaluate_strategy(market_series, indicator_series)
    outcome_series = compute_signal_outcomes(market_series, evaluation_series)
    buy_date = next(e.date for e in evaluation_series.evaluations if e.decision.value == "BUY")
    domain_audit = build_strategy_audit(market_series, evaluation_series, outcome_series, indicator_series, buy_date)

    response = client.get(
        "/api/v1/audits/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-04-30", "interval": "1d", "audit_date": buy_date.isoformat()},
    )
    body = response.json()

    assert body["evaluation"]["decision"] == domain_audit.evaluation.decision.value
    assert len(body["evaluation"]["conditions"]) == len(domain_audit.evaluation.conditions)
    assert body["historical_evidence"]["prior_signal_count"] == domain_audit.historical_evidence.prior_signal_count
    assert body["historical_evidence"]["five_bar"]["eligible_outcome_count"] == domain_audit.historical_evidence.five_bar.eligible_outcome_count
    assert body["historical_evidence"]["ten_bar"]["eligible_outcome_count"] == domain_audit.historical_evidence.ten_bar.eligible_outcome_count
    assert body["historical_signal_risk"]["eligible_outcome_count"] == domain_audit.historical_signal_risk.eligible_outcome_count
    assert body["historical_signal_risk"]["average_mae_10d"] == domain_audit.historical_signal_risk.average_mae_10d
    assert body["risk_market_context"]["annualized_realized_volatility_20"] == domain_audit.risk_market_context.annualized_realized_volatility_20
    assert body["risk_market_context"]["regime"] == domain_audit.risk_market_context.regime.value
    assert body["retrospective_outcome"]["reference_close"] == domain_audit.retrospective_outcome.reference_close
    assert body["retrospective_outcome"]["mae_10d"] == domain_audit.retrospective_outcome.mae_10d


def test_decimal_values_and_signs_unchanged_zero_and_null_preserved(client):
    audit_date = _find_date_for_decision(client, "BUY")
    response = client.get(
        "/api/v1/audits/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d", "audit_date": audit_date},
    )
    body = response.json()
    hit_rate = body["historical_evidence"]["ten_bar"]["hit_rate"]
    if hit_rate is not None:
        assert 0.0 <= hit_rate <= 1.0  # decimal fraction, never *100
    mae = body["historical_signal_risk"]["worst_mae_10d"]
    if mae is not None:
        assert -1.0 < mae < 1.0  # never abs()'d away from a natural sign, never *100
    vol = body["risk_market_context"]["annualized_realized_volatility_20"]
    assert vol is None or isinstance(vol, (int, float))


def test_deterministic_repeated_response(client):
    audit_date = _find_date_for_decision(client, "BUY")
    params = {"start": "2024-01-01", "end": "2024-03-30", "interval": "1d", "audit_date": audit_date}
    r1 = client.get("/api/v1/audits/trend-momentum-v1/RELIANCE", params=params)
    r2 = client.get("/api/v1/audits/trend-momentum-v1/RELIANCE", params=params)
    assert r1.json() == r2.json()


def test_single_market_fetch(client, fake_market_data_service):
    audit_date = fake_market_data_service._series.bars[60].date.isoformat()
    client.get(
        "/api/v1/audits/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d", "audit_date": audit_date},
    )
    assert len(fake_market_data_service.calls) == 1


# ---------------------------------------------------------------------------
# Error contract
# ---------------------------------------------------------------------------


def test_malformed_audit_date_returns_request_validation_error(client):
    response = client.get(
        "/api/v1/audits/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d", "audit_date": "not-a-date"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_missing_audit_date_returns_request_validation_error(client):
    response = client.get(
        "/api/v1/audits/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d"},
    )
    assert response.status_code == 422


def test_audit_date_not_a_trading_bar_rejected_not_silently_remapped():
    # A custom series with a genuine weekend gap: 2024-01-05 (Fri) then
    # 2024-01-08 (Mon) -- 2024-01-06/07 (Sat/Sun) have no bar at all.
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(5)] + [
        date(2024, 1, 8) + timedelta(days=i) for i in range(5)
    ]
    bars = tuple(OHLCVBar(date=d, open=100, high=105, low=95, close=100, adj_close=100, volume=1000) for d in dates)
    series = OHLCVSeries(provider_symbol="RELIANCE.NS", interval="1d", bars=bars)
    service = FakeMarketDataService(series=series)
    app.dependency_overrides[get_market_data_service] = lambda: service

    from fastapi.testclient import TestClient

    with TestClient(app) as gapped_client:
        response = gapped_client.get(
            "/api/v1/audits/trend-momentum-v1/RELIANCE",
            params={"start": "2024-01-01", "end": "2024-01-12", "interval": "1d", "audit_date": "2024-01-06"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AUDIT_DATE_NOT_A_TRADING_BAR"


def test_audit_date_outside_requested_range_rejected(client):
    audit_date = _find_date_for_decision(client, "BUY")
    response = client.get(
        "/api/v1/audits/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-01-05", "interval": "1d", "audit_date": audit_date},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AUDIT_DATE_NOT_A_TRADING_BAR"


def test_unsupported_interval_rejected(client):
    response = client.get(
        "/api/v1/audits/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1h", "audit_date": "2024-01-05"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_INTERVAL"


def test_unknown_symbol_follows_existing_error_contract(client):
    failing_service = FakeMarketDataService(raise_exc=InstrumentNotFoundError("NOTASYMBOL"))
    app.dependency_overrides[get_market_data_service] = lambda: failing_service
    response = client.get(
        "/api/v1/audits/trend-momentum-v1/NOTASYMBOL",
        params={"start": "2024-01-01", "end": "2024-01-10", "interval": "1d", "audit_date": "2024-01-05"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "INSTRUMENT_NOT_FOUND"


def test_error_body_never_exposes_traceback(client):
    response = client.get(
        "/api/v1/audits/trend-momentum-v1/RELIANCE",
        params={"start": "2024-01-01", "end": "2024-03-30", "interval": "1d", "audit_date": "not-a-date"},
    )
    assert "Traceback" not in response.text
    assert set(response.json().keys()) == {"error"}
    assert set(response.json()["error"].keys()) == {"code", "message"}


# ---------------------------------------------------------------------------
# API-level look-ahead integration test
# ---------------------------------------------------------------------------


def test_api_future_price_mutation_does_not_change_point_in_time_sections():
    series_a = make_market_series(n=90)
    audit_index = 60
    audit_date = series_a.bars[audit_index].date

    bars_b = list(series_a.bars)
    for j in range(audit_index + 1, len(bars_b)):
        b = bars_b[j]
        bars_b[j] = OHLCVBar(date=b.date, open=99999, high=99999, low=99999, close=99999, adj_close=99999, volume=1)
    series_b = OHLCVSeries(provider_symbol=series_a.provider_symbol, interval=series_a.interval, bars=tuple(bars_b))

    service_a = FakeMarketDataService(series=series_a)
    service_b = FakeMarketDataService(series=series_b)

    app.dependency_overrides[get_market_data_service] = lambda: service_a
    from fastapi.testclient import TestClient

    with TestClient(app) as client_a:
        response_a = client_a.get(
            "/api/v1/audits/trend-momentum-v1/RELIANCE",
            params={"start": "2024-01-01", "end": "2024-12-31", "interval": "1d", "audit_date": audit_date.isoformat()},
        )

    app.dependency_overrides[get_market_data_service] = lambda: service_b
    with TestClient(app) as client_b:
        response_b = client_b.get(
            "/api/v1/audits/trend-momentum-v1/RELIANCE",
            params={"start": "2024-01-01", "end": "2024-12-31", "interval": "1d", "audit_date": audit_date.isoformat()},
        )
    app.dependency_overrides.clear()

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    body_a, body_b = response_a.json(), response_b.json()

    assert body_a["evaluation"] == body_b["evaluation"]
    assert body_a["historical_evidence"] == body_b["historical_evidence"]
    assert body_a["historical_signal_risk"] == body_b["historical_signal_risk"]
    assert body_a["risk_market_context"] == body_b["risk_market_context"]
    # Retrospective outcome is allowed to differ (hindsight-sensitive).


# ---------------------------------------------------------------------------
# Calculation history vs historical evidence window (mandatory regression
# test for the post-3D-manual-verification correction).
# ---------------------------------------------------------------------------


def _make_repeating_cycle_series(n_cycles: int, cycle_len: int = 90, start: date = date(2024, 1, 1)) -> OHLCVSeries:
    """Repeats `make_market_series`'s exact 90-day warm-up/uptrend/reversal
    shape every `cycle_len` days (each cycle restarting at close=100), so a
    250+ day series stays positive AND produces real BUY signals spread
    throughout its full history -- unlike calling `make_market_series`
    itself with a large `n` (its unbounded post-reversal downtrend goes
    negative well before day 250)."""

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


def test_narrow_start_no_longer_starves_audit_date_decision():
    """Reproduces the exact reported bug: a narrow `start` close to
    audit_date must no longer starve SMA50 warm-up and flip a real
    decision into a fabricated INSUFFICIENT_DATA. Both a wide and a
    narrow (but otherwise valid) `start` must now produce the SAME
    decision and the SAME pass/fail outcome per condition.

    (Exact bit-for-bit numeric equality of RSI14's evidence value is NOT
    asserted here: Wilder's RSI is a recursive/exponentially-weighted
    filter, not a fixed trailing window like SMA, so it never perfectly
    "forgets" data further back than the fetched series start -- two
    genuinely different amounts of extra history can produce a tiny,
    financially immaterial floating-point difference in the RSI value
    itself. See the next test for a scenario with a mathematically
    guaranteed bit-identical result.)"""
    series = _make_repeating_cycle_series(n_cycles=3)
    audit_date = series.bars[200].date
    end_date = series.bars[-1].date
    wide_start = series.bars[0].date
    narrow_start = series.bars[190].date  # 10 calendar days before audit_date

    service = FakeMarketDataService(series=series)
    app.dependency_overrides[get_market_data_service] = lambda: service
    try:
        response_wide = client_get_audit("RELIANCE", wide_start, end_date, audit_date)
        response_narrow = client_get_audit("RELIANCE", narrow_start, end_date, audit_date)
    finally:
        app.dependency_overrides.clear()

    assert response_wide.status_code == 200
    assert response_narrow.status_code == 200
    body_wide, body_narrow = response_wide.json(), response_narrow.json()

    assert body_wide["evaluation"]["decision"] == body_narrow["evaluation"]["decision"]
    assert body_wide["evaluation"]["decision"] != "INSUFFICIENT_DATA"  # confirms real warm-up was available
    wide_passed = [(c["condition_id"], c["passed"]) for c in body_wide["evaluation"]["conditions"]]
    narrow_passed = [(c["condition_id"], c["passed"]) for c in body_narrow["evaluation"]["conditions"]]
    assert wide_passed == narrow_passed
    assert body_wide["risk_market_context"]["regime"] == body_narrow["risk_market_context"]["regime"]

    # The evidence population is legitimately allowed (expected) to differ.
    assert body_narrow["historical_evidence"]["prior_signal_count"] <= body_wide["historical_evidence"]["prior_signal_count"]


def test_two_starts_within_the_same_warmup_clamp_produce_bit_identical_calculation_sections():
    """When two DIFFERENT requested starts both fall within the internal
    warm-up clamp zone (i.e. both are closer to audit_date than
    CALCULATION_WARMUP_CALENDAR_DAYS), the resolved calculation window is
    IDENTICAL for both -- so `evaluation` and `risk_market_context` are
    not just equal, they are computed from byte-identical underlying data
    and must match exactly, while the evidence population still legitimately
    differs (different requested start)."""
    series = _make_repeating_cycle_series(n_cycles=3)
    audit_date = series.bars[200].date
    end_date = series.bars[-1].date
    start_a = audit_date - timedelta(days=10)
    start_b = audit_date - timedelta(days=30)
    assert start_a != start_b

    service = FakeMarketDataService(series=series)
    app.dependency_overrides[get_market_data_service] = lambda: service
    try:
        response_a = client_get_audit("RELIANCE", start_a, end_date, audit_date)
        response_b = client_get_audit("RELIANCE", start_b, end_date, audit_date)
    finally:
        app.dependency_overrides.clear()

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    body_a, body_b = response_a.json(), response_b.json()

    assert body_a["evaluation"] == body_b["evaluation"]
    assert body_a["risk_market_context"] == body_b["risk_market_context"]
    # historical_evidence MAY still differ (different requested start) --
    # not asserted equal or unequal here, only the calculation sections.


def test_warmup_only_buys_before_requested_start_never_enter_evidence_population():
    """Direct domain-level proof: any BUY evaluation strictly before the
    requested (narrow) start -- even though it's present in the internally
    fetched calculation series -- must never be counted."""
    series = _make_repeating_cycle_series(n_cycles=3)
    audit_date = series.bars[200].date
    narrow_start = series.bars[190].date

    indicator_series = compute_indicators(series)
    evaluation_series = evaluate_strategy(series, indicator_series)
    outcome_series = compute_signal_outcomes(series, evaluation_series)

    # Ground truth: count BUYs with narrow_start <= date < audit_date directly.
    expected_prior_count = sum(
        1 for e in evaluation_series.evaluations
        if narrow_start <= e.date < audit_date and e.decision.value == "BUY"
    )
    # And confirm there is at least one warm-up-only BUY strictly BEFORE
    # narrow_start, so this test actually exercises the exclusion.
    warmup_only_buys = [
        e for e in evaluation_series.evaluations if e.date < narrow_start and e.decision.value == "BUY"
    ]
    assert len(warmup_only_buys) > 0, "fixture does not exercise the warm-up-exclusion path"

    audit = build_strategy_audit(
        series, evaluation_series, outcome_series, indicator_series, audit_date, evidence_start_date=narrow_start
    )

    assert audit.historical_evidence.prior_signal_count == expected_prior_count
    assert audit.historical_evidence.prior_signal_count < len(
        [e for e in evaluation_series.evaluations if e.date < audit_date and e.decision.value == "BUY"]
    )


def client_get_audit(symbol: str, start: date, end: date, audit_date: date):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        return c.get(
            f"/api/v1/audits/trend-momentum-v1/{symbol}",
            params={"start": start.isoformat(), "end": end.isoformat(), "interval": "1d", "audit_date": audit_date.isoformat()},
        )
