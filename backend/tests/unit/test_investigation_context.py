"""Phase 4C: signal-time context & FAILED/NON_FAILED association engine
tests.

Builds `OHLCVSeries`/`IndicatorSeries` fixtures directly (hand-set
sma20/sma50/rsi14 per date) and `SignalInvestigationDataset` fixtures
directly (the accepted Phase 4A boundary) -- Phase 4C never recomputes
Phase 2A outcomes or Phase 3B regime/volatility formulas, so tests focus
on the join/validation/aggregation this module adds.
"""

from __future__ import annotations

import copy
from datetime import date, timedelta

import pytest

from app.audit.engine import build_risk_market_context
from app.audit.models import MarketRegime
from app.core.exceptions import InvestigationInputInvalidError
from app.indicators.models import IndicatorRow, IndicatorSeries
from app.investigation.context import build_failure_context_dataset
from app.investigation.models import SignalInvestigationClassification, SignalInvestigationDataset, SignalInvestigationObservation
from app.market_data.models import OHLCVBar, OHLCVSeries

SYMBOL = "X.NS"
INTERVAL = "1d"
STRATEGY_ID = "trend_momentum_v1"
STRATEGY_NAME = "Trend + Momentum v1"

POSITIVE = SignalInvestigationClassification.POSITIVE
NEGATIVE = SignalInvestigationClassification.NEGATIVE
BREAKEVEN = SignalInvestigationClassification.BREAKEVEN
UNAVAILABLE = SignalInvestigationClassification.UNAVAILABLE

N_BARS = 30


def _dates(n: int = N_BARS, start: date = date(2024, 1, 1)) -> list[date]:
    return [start + timedelta(days=i) for i in range(n)]


def _closes(n: int = N_BARS) -> list[float]:
    return [1000.0 + i for i in range(n)]


def _market(dates: list[date], closes: list[float], symbol: str = SYMBOL, interval: str = INTERVAL) -> OHLCVSeries:
    bars = tuple(
        OHLCVBar(date=d, open=c, high=c + 5, low=c - 5, close=c, adj_close=c, volume=1000) for d, c in zip(dates, closes)
    )
    return OHLCVSeries(provider_symbol=symbol, interval=interval, bars=bars)


def _indicators(
    dates: list[date],
    rows_spec: list[tuple[float | None, float | None, float | None]],
    symbol: str = SYMBOL,
    interval: str = INTERVAL,
) -> IndicatorSeries:
    rows = tuple(
        IndicatorRow(date=d, sma20=sma20, sma50=sma50, rsi14=rsi14, average_volume=None, volume_ratio=None)
        for d, (sma20, sma50, rsi14) in zip(dates, rows_spec)
    )
    return IndicatorSeries(provider_symbol=symbol, interval=interval, rows=rows)


def _valid_rows(closes: list[float]) -> list[tuple[float, float, float]]:
    """Default valid BUY-consistent (sma20, sma50, rsi14) per index --
    close > sma20 > sma50 (margin 10/20) and RSI14 = 55.0 (mid-range)."""
    return [(c - 10.0, c - 20.0, 55.0) for c in closes]


def _obs(
    d: date,
    classification: SignalInvestigationClassification,
    forward_return_10d: float | None = 0.01,
    mae_10d: float | None = -0.01,
    mfe_10d: float | None = 0.02,
) -> SignalInvestigationObservation:
    """Phase 4A observation fixture -- Phase 4C never reads
    reference_close/forward_close_5d/forward_return_5d/available_forward_bars,
    so those are left at simple placeholder values."""
    present = classification != UNAVAILABLE
    return SignalInvestigationObservation(
        signal_date=d,
        classification=classification,
        reference_close=100.0,
        forward_close_5d=101.0 if present else None,
        forward_return_5d=0.01 if present else None,
        forward_close_10d=100.0 * (1 + forward_return_10d) if present and forward_return_10d is not None else None,
        forward_return_10d=forward_return_10d if present else None,
        mae_10d=mae_10d if present else None,
        mfe_10d=mfe_10d if present else None,
        available_forward_bars=15 if present else 2,
    )


def _investigation_dataset(
    observations: tuple[SignalInvestigationObservation, ...], symbol: str = SYMBOL, interval: str = INTERVAL
) -> SignalInvestigationDataset:
    positive = sum(1 for o in observations if o.classification == POSITIVE)
    negative = sum(1 for o in observations if o.classification == NEGATIVE)
    breakeven = sum(1 for o in observations if o.classification == BREAKEVEN)
    unavailable = sum(1 for o in observations if o.classification == UNAVAILABLE)
    return SignalInvestigationDataset(
        provider_symbol=symbol,
        interval=interval,
        strategy_id=STRATEGY_ID,
        strategy_name=STRATEGY_NAME,
        observations=observations,
        total_signal_count=len(observations),
        eligible_count=positive + negative + breakeven,
        positive_count=positive,
        negative_count=negative,
        breakeven_count=breakeven,
        unavailable_count=unavailable,
    )


def _single_signal_fixture(index: int, sma20: float | None, sma50: float | None, rsi14: float | None):
    """Builds a full (dataset, market, indicators) triple with ONE POSITIVE
    observation at `dates[index]`, with the given indicator row overridden
    at that index (all other rows use `_valid_rows`)."""
    dates = _dates()
    closes = _closes()
    rows = _valid_rows(closes)
    rows[index] = (sma20, sma50, rsi14)
    market = _market(dates, closes)
    indicators = _indicators(dates, rows)
    dataset = _investigation_dataset((_obs(dates[index], POSITIVE),))
    return dataset, market, indicators, dates[index]


# ---------------------------------------------------------------------------
# Section 13: feature calculation
# ---------------------------------------------------------------------------


def test_rsi_copied_exactly_from_indicator_series():
    dataset, market, indicators, d = _single_signal_fixture(25, sma20=1000.0, sma50=900.0, rsi14=54.37)
    result = build_failure_context_dataset(dataset, market, indicators)
    assert result.observations[0].rsi14 == 54.37


def test_close_copied_exactly_from_signal_date_ohlcv():
    dataset, market, indicators, d = _single_signal_fixture(25, sma20=1000.0, sma50=900.0, rsi14=55.0)
    result = build_failure_context_dataset(dataset, market, indicators)
    assert result.observations[0].close == 1025.0  # closes()[25] == 1000 + 25


def test_sma20_copied_exactly():
    dataset, market, indicators, d = _single_signal_fixture(25, sma20=1000.0, sma50=900.0, rsi14=55.0)
    result = build_failure_context_dataset(dataset, market, indicators)
    assert result.observations[0].sma20 == 1000.0


def test_sma50_copied_exactly():
    dataset, market, indicators, d = _single_signal_fixture(25, sma20=1000.0, sma50=900.0, rsi14=55.0)
    result = build_failure_context_dataset(dataset, market, indicators)
    assert result.observations[0].sma50 == 900.0


def test_close_above_sma20_fraction_exact():
    dataset, market, indicators, d = _single_signal_fixture(25, sma20=1000.0, sma50=900.0, rsi14=55.0)
    result = build_failure_context_dataset(dataset, market, indicators)
    close = 1025.0
    sma20 = 1000.0
    assert result.observations[0].close_above_sma20_fraction == pytest.approx(close / sma20 - 1)


def test_sma20_above_sma50_fraction_exact():
    dataset, market, indicators, d = _single_signal_fixture(25, sma20=1000.0, sma50=900.0, rsi14=55.0)
    result = build_failure_context_dataset(dataset, market, indicators)
    assert result.observations[0].sma20_above_sma50_fraction == pytest.approx(1000.0 / 900.0 - 1)


def test_no_percentage_conversion_fraction_stays_decimal():
    dataset, market, indicators, d = _single_signal_fixture(25, sma20=1000.0, sma50=900.0, rsi14=55.0)
    result = build_failure_context_dataset(dataset, market, indicators)
    # close/sma20 fraction ~0.025, sma20/sma50 fraction ~0.111 -- both « 1,
    # never *100 (which would give ~2.5 / ~11.1).
    assert result.observations[0].close_above_sma20_fraction < 1
    assert result.observations[0].sma20_above_sma50_fraction < 1


def test_no_rounding_full_precision_preserved():
    dataset, market, indicators, d = _single_signal_fixture(25, sma20=987.654321, sma50=900.0, rsi14=61.23456789)
    result = build_failure_context_dataset(dataset, market, indicators)
    assert result.observations[0].rsi14 == 61.23456789
    assert result.observations[0].close_above_sma20_fraction == 1025.0 / 987.654321 - 1


def test_trend_distance_fractions_never_abs_stay_naturally_positive():
    # A valid BUY structurally requires close > sma20 > sma50, so both
    # fractions are naturally strictly positive without any abs() applied.
    dataset, market, indicators, d = _single_signal_fixture(25, sma20=1000.0, sma50=900.0, rsi14=55.0)
    result = build_failure_context_dataset(dataset, market, indicators)
    assert result.observations[0].close_above_sma20_fraction > 0
    assert result.observations[0].sma20_above_sma50_fraction > 0


def test_volatility_exactly_matches_accepted_phase3b_result():
    dataset, market, indicators, d = _single_signal_fixture(25, sma20=1000.0, sma50=900.0, rsi14=55.0)
    result = build_failure_context_dataset(dataset, market, indicators)
    expected = build_risk_market_context(market, indicators, d)
    assert result.observations[0].annualized_realized_volatility_20 == expected.annualized_realized_volatility_20


def test_regime_exactly_matches_accepted_phase3b_result():
    dataset, market, indicators, d = _single_signal_fixture(25, sma20=1000.0, sma50=900.0, rsi14=55.0)
    result = build_failure_context_dataset(dataset, market, indicators)
    expected = build_risk_market_context(market, indicators, d)
    assert result.observations[0].regime == expected.regime == MarketRegime.BULLISH_TREND


# ---------------------------------------------------------------------------
# Section 14: structural BUY invariants
# ---------------------------------------------------------------------------


def test_close_below_sma20_rejected():
    dataset, market, indicators, _ = _single_signal_fixture(25, sma20=1100.0, sma50=900.0, rsi14=55.0)  # close(1025) < sma20
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_context_dataset(dataset, market, indicators)


def test_close_equal_sma20_rejected():
    dataset, market, indicators, _ = _single_signal_fixture(25, sma20=1025.0, sma50=900.0, rsi14=55.0)  # close == sma20
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_context_dataset(dataset, market, indicators)


def test_sma20_below_sma50_rejected():
    dataset, market, indicators, _ = _single_signal_fixture(25, sma20=900.0, sma50=1000.0, rsi14=55.0)
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_context_dataset(dataset, market, indicators)


def test_sma20_equal_sma50_rejected():
    dataset, market, indicators, _ = _single_signal_fixture(25, sma20=950.0, sma50=950.0, rsi14=55.0)
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_context_dataset(dataset, market, indicators)


def test_rsi_below_40_rejected():
    dataset, market, indicators, _ = _single_signal_fixture(25, sma20=1000.0, sma50=900.0, rsi14=39.9)
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_context_dataset(dataset, market, indicators)


def test_rsi_above_70_rejected():
    dataset, market, indicators, _ = _single_signal_fixture(25, sma20=1000.0, sma50=900.0, rsi14=70.1)
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_context_dataset(dataset, market, indicators)


def test_missing_rsi_rejected():
    dataset, market, indicators, _ = _single_signal_fixture(25, sma20=1000.0, sma50=900.0, rsi14=None)
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_context_dataset(dataset, market, indicators)


def test_missing_sma20_rejected():
    dataset, market, indicators, _ = _single_signal_fixture(25, sma20=None, sma50=900.0, rsi14=55.0)
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_context_dataset(dataset, market, indicators)


def test_missing_sma50_rejected():
    dataset, market, indicators, _ = _single_signal_fixture(25, sma20=1000.0, sma50=None, rsi14=55.0)
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_context_dataset(dataset, market, indicators)


def test_rsi_exactly_40_is_valid_inclusive_boundary():
    dataset, market, indicators, _ = _single_signal_fixture(25, sma20=1000.0, sma50=900.0, rsi14=40.0)
    result = build_failure_context_dataset(dataset, market, indicators)
    assert result.observations[0].rsi14 == 40.0


def test_rsi_exactly_70_is_valid_inclusive_boundary():
    dataset, market, indicators, _ = _single_signal_fixture(25, sma20=1000.0, sma50=900.0, rsi14=70.0)
    result = build_failure_context_dataset(dataset, market, indicators)
    assert result.observations[0].rsi14 == 70.0


# ---------------------------------------------------------------------------
# Section 15: population association
# ---------------------------------------------------------------------------


def test_population_association_mixed_fixture():
    dates = _dates()
    closes = _closes()
    rows = _valid_rows(closes)

    # Indices 20-22: NEGATIVE, RSI 45/50/41.
    rows[20] = (990.0, 900.0, 45.0)
    rows[21] = (1005.0, 950.0, 50.0)
    rows[22] = (1010.0, 990.0, 41.0)
    # Indices 23-25: POSITIVE, RSI 60/65/58.
    rows[23] = (1000.0, 900.0, 60.0)
    rows[24] = (1010.0, 950.0, 65.0)
    rows[25] = (1015.0, 990.0, 58.0)
    # Index 26: BREAKEVEN, RSI 55.
    rows[26] = (1010.0, 950.0, 55.0)
    # Index 27: UNAVAILABLE (still needs a valid signal-time context).
    rows[27] = (1010.0, 950.0, 52.0)

    market = _market(dates, closes)
    indicators = _indicators(dates, rows)

    observations = (
        _obs(dates[20], NEGATIVE),
        _obs(dates[21], NEGATIVE),
        _obs(dates[22], NEGATIVE),
        _obs(dates[23], POSITIVE),
        _obs(dates[24], POSITIVE),
        _obs(dates[25], POSITIVE),
        _obs(dates[26], BREAKEVEN),
        _obs(dates[27], UNAVAILABLE),
    )
    dataset = _investigation_dataset(observations)

    result = build_failure_context_dataset(dataset, market, indicators)

    # --- counts -------------------------------------------------------
    assert result.failed_count == 3
    assert result.non_failed_count == 4  # 3 POSITIVE + 1 BREAKEVEN
    assert result.unavailable_count == 1
    assert result.eligible_count == 7
    assert result.total_signal_count == 8
    assert len(result.observations) == 8  # every Phase 4A observation represented, including UNAVAILABLE

    # --- FAILED RSI: [45, 50, 41] -> sorted [41, 45, 50] -> median 45 ---
    failed_rsi = [45.0, 50.0, 41.0]
    assert result.failed.count == 3
    assert result.failed.average_rsi14 == pytest.approx(sum(failed_rsi) / 3)
    assert result.failed.median_rsi14 == pytest.approx(45.0)

    # --- NON_FAILED RSI: [60, 65, 58, 55] (POSITIVE x3 + BREAKEVEN) -----
    # sorted [55, 58, 60, 65] -> median (58+60)/2 = 59
    non_failed_rsi = [60.0, 65.0, 58.0, 55.0]
    assert result.non_failed.count == 4
    assert result.non_failed.average_rsi14 == pytest.approx(sum(non_failed_rsi) / 4)
    assert result.non_failed.median_rsi14 == pytest.approx(59.0)

    # --- close/SMA20 and SMA20/SMA50 fractions, independently computed -
    def frac(close: float, sma: float) -> float:
        return close / sma - 1

    failed_close_fracs = [frac(1020.0, 990.0), frac(1021.0, 1005.0), frac(1022.0, 1010.0)]
    assert result.failed.average_close_above_sma20_fraction == pytest.approx(sum(failed_close_fracs) / 3)

    failed_sma_fracs = [frac(990.0, 900.0), frac(1005.0, 950.0), frac(1010.0, 990.0)]
    assert result.failed.average_sma20_above_sma50_fraction == pytest.approx(sum(failed_sma_fracs) / 3)

    # --- regime counts: every valid observation is BULLISH_TREND -------
    assert result.failed.bullish_trend_count == 3
    assert result.failed.bearish_trend_count == 0
    assert result.non_failed.bullish_trend_count == 4

    # --- volatility: cross-checked against the real Phase 3B function --
    expected_failed_vols = [
        build_risk_market_context(market, indicators, dates[i]).annualized_realized_volatility_20 for i in (20, 21, 22)
    ]
    assert all(v is not None for v in expected_failed_vols)
    assert result.failed.volatility_available_count == 3
    assert result.failed.volatility_unavailable_count == 0
    assert result.failed.average_annualized_realized_volatility_20 == pytest.approx(
        sum(expected_failed_vols) / len(expected_failed_vols)
    )

    # --- BREAKEVEN participates in NON_FAILED, UNAVAILABLE in neither ---
    non_failed_dates = {o.signal_date for o in result.observations if o.classification in (POSITIVE, BREAKEVEN)}
    assert dates[26] in non_failed_dates
    unavailable_context = next(o for o in result.observations if o.signal_date == dates[27])
    assert unavailable_context.classification == UNAVAILABLE
    # UNAVAILABLE's own RSI (52.0) must not appear in either summary's average.
    assert 52.0 not in failed_rsi
    assert 52.0 not in non_failed_rsi


# ---------------------------------------------------------------------------
# Section 16: empty / missing cases
# ---------------------------------------------------------------------------


def test_no_failed_observations():
    dates = _dates()
    closes = _closes()
    rows = _valid_rows(closes)
    market = _market(dates, closes)
    indicators = _indicators(dates, rows)
    dataset = _investigation_dataset((_obs(dates[25], POSITIVE),))
    result = build_failure_context_dataset(dataset, market, indicators)
    assert result.failed.count == 0
    assert result.failed.average_rsi14 is None
    assert result.failed.median_rsi14 is None
    assert result.failed.volatility_available_count == 0
    assert result.failed.volatility_unavailable_count == 0
    assert result.failed.bullish_trend_count == 0


def test_no_non_failed_observations():
    dates = _dates()
    closes = _closes()
    rows = _valid_rows(closes)
    market = _market(dates, closes)
    indicators = _indicators(dates, rows)
    dataset = _investigation_dataset((_obs(dates[25], NEGATIVE),))
    result = build_failure_context_dataset(dataset, market, indicators)
    assert result.non_failed.count == 0
    assert result.non_failed.average_rsi14 is None
    assert result.non_failed.average_close_above_sma20_fraction is None


def test_empty_dataset_produces_valid_empty_result():
    dates = _dates()
    closes = _closes()
    rows = _valid_rows(closes)
    market = _market(dates, closes)
    indicators = _indicators(dates, rows)
    dataset = _investigation_dataset(())
    result = build_failure_context_dataset(dataset, market, indicators)
    assert result.total_signal_count == 0
    assert result.eligible_count == 0
    assert result.unavailable_count == 0
    assert result.observations == ()
    assert result.failed.count == 0
    assert result.non_failed.count == 0


def test_all_volatility_unavailable_in_one_population():
    # Indices < 20 never have 21 closes of history -> volatility always None.
    dates = _dates()
    closes = _closes()
    rows = _valid_rows(closes)
    market = _market(dates, closes)
    indicators = _indicators(dates, rows)
    dataset = _investigation_dataset((_obs(dates[3], NEGATIVE), _obs(dates[5], NEGATIVE)))
    result = build_failure_context_dataset(dataset, market, indicators)
    assert result.failed.count == 2
    assert result.failed.volatility_available_count == 0
    assert result.failed.volatility_unavailable_count == 2
    assert result.failed.average_annualized_realized_volatility_20 is None
    assert result.failed.median_annualized_realized_volatility_20 is None


def test_mixed_available_and_unavailable_volatility_in_one_population():
    dates = _dates()
    closes = _closes()
    rows = _valid_rows(closes)
    market = _market(dates, closes)
    indicators = _indicators(dates, rows)
    # Index 5 (<20): volatility unavailable. Index 25 (>=20): available.
    dataset = _investigation_dataset((_obs(dates[5], NEGATIVE), _obs(dates[25], NEGATIVE)))
    result = build_failure_context_dataset(dataset, market, indicators)
    assert result.failed.count == 2
    assert result.failed.volatility_available_count == 1
    assert result.failed.volatility_unavailable_count == 1
    expected = build_risk_market_context(market, indicators, dates[25]).annualized_realized_volatility_20
    assert result.failed.average_annualized_realized_volatility_20 == pytest.approx(expected)
    assert result.failed.median_annualized_realized_volatility_20 == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Section 17: alignment
# ---------------------------------------------------------------------------


def test_signal_date_absent_from_market_series_rejected():
    dates = _dates()
    closes = _closes()
    rows = _valid_rows(closes)
    market = _market(dates, closes)
    indicators = _indicators(dates, rows)
    dataset = _investigation_dataset((_obs(date(2099, 1, 1), NEGATIVE),))
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_context_dataset(dataset, market, indicators)


def test_symbol_mismatch_between_dataset_and_market_rejected():
    dates = _dates()
    closes = _closes()
    rows = _valid_rows(closes)
    market = _market(dates, closes, symbol="OTHER.NS")
    indicators = _indicators(dates, rows)
    dataset = _investigation_dataset((_obs(dates[25], NEGATIVE),))
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_context_dataset(dataset, market, indicators)


def test_interval_mismatch_between_dataset_and_indicators_rejected():
    dates = _dates()
    closes = _closes()
    rows = _valid_rows(closes)
    market = _market(dates, closes)
    indicators = _indicators(dates, rows, interval="1wk")
    dataset = _investigation_dataset((_obs(dates[25], NEGATIVE),))
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_context_dataset(dataset, market, indicators)


def test_market_indicator_length_mismatch_rejected():
    dates = _dates()
    closes = _closes()
    rows = _valid_rows(closes)
    market = _market(dates, closes)
    indicators = _indicators(dates[:-1], rows[:-1])  # one row short
    dataset = _investigation_dataset((_obs(dates[25], NEGATIVE),))
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_context_dataset(dataset, market, indicators)


def test_market_indicator_date_misalignment_rejected():
    dates = _dates()
    closes = _closes()
    rows = _valid_rows(closes)
    market = _market(dates, closes)
    shifted_dates = [dates[0]] + dates[2:] + [dates[-1] + timedelta(days=1)]  # misaligned dates, same length
    indicators = _indicators(shifted_dates, rows)
    dataset = _investigation_dataset((_obs(dates[25], NEGATIVE),))
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_context_dataset(dataset, market, indicators)


# ---------------------------------------------------------------------------
# Section 18: determinism / non-mutation
# ---------------------------------------------------------------------------


def test_deterministic_repeated_execution():
    dates = _dates()
    closes = _closes()
    rows = _valid_rows(closes)
    market = _market(dates, closes)
    indicators = _indicators(dates, rows)
    dataset = _investigation_dataset((_obs(dates[20], NEGATIVE), _obs(dates[25], POSITIVE)))

    first = build_failure_context_dataset(dataset, market, indicators)
    second = build_failure_context_dataset(dataset, market, indicators)
    assert first == second


def test_no_input_mutation():
    dates = _dates()
    closes = _closes()
    rows = _valid_rows(closes)
    market = _market(dates, closes)
    indicators = _indicators(dates, rows)
    dataset = _investigation_dataset((_obs(dates[20], NEGATIVE), _obs(dates[25], POSITIVE)))

    market_before = copy.deepcopy(market)
    indicators_before = copy.deepcopy(indicators)
    dataset_before = copy.deepcopy(dataset)

    build_failure_context_dataset(dataset, market, indicators)

    assert market == market_before
    assert indicators == indicators_before
    assert dataset == dataset_before


# ---------------------------------------------------------------------------
# Section 10 (critical): point-in-time isolation
# ---------------------------------------------------------------------------


def test_context_unaffected_by_mutating_data_after_signal_date():
    dates = _dates()
    closes = _closes()
    rows = _valid_rows(closes)
    signal_index = 22
    market = _market(dates, closes)
    indicators = _indicators(dates, rows)
    dataset = _investigation_dataset((_obs(dates[signal_index], NEGATIVE),))

    before = build_failure_context_dataset(dataset, market, indicators).observations[0]

    # Mutate ONLY bars/rows strictly AFTER the signal date.
    mutated_closes = list(closes)
    for i in range(signal_index + 1, N_BARS):
        mutated_closes[i] = mutated_closes[i] * 5 + 999  # drastic future change
    mutated_rows = list(rows)
    for i in range(signal_index + 1, N_BARS):
        mutated_rows[i] = (mutated_closes[i] + 500.0, mutated_closes[i] + 100.0, 20.0)  # wildly different future indicators

    mutated_market = _market(dates, mutated_closes)
    mutated_indicators = _indicators(dates, mutated_rows)

    after = build_failure_context_dataset(dataset, mutated_market, mutated_indicators).observations[0]

    assert after.regime == before.regime
    assert after.annualized_realized_volatility_20 == before.annualized_realized_volatility_20
    assert after.rsi14 == before.rsi14
    assert after.close == before.close
    assert after.sma20 == before.sma20
    assert after.sma50 == before.sma50
    assert after.close_above_sma20_fraction == before.close_above_sma20_fraction
    assert after.sma20_above_sma50_fraction == before.sma20_above_sma50_fraction


# ---------------------------------------------------------------------------
# Population invariants (section 12) against a tampered Phase 4A dataset
# ---------------------------------------------------------------------------


def test_mismatched_negative_count_rejected():
    dates = _dates()
    closes = _closes()
    rows = _valid_rows(closes)
    market = _market(dates, closes)
    indicators = _indicators(dates, rows)
    good = _investigation_dataset((_obs(dates[20], NEGATIVE), _obs(dates[25], POSITIVE)))
    tampered = SignalInvestigationDataset(
        provider_symbol=good.provider_symbol,
        interval=good.interval,
        strategy_id=good.strategy_id,
        strategy_name=good.strategy_name,
        observations=good.observations,
        total_signal_count=good.total_signal_count,
        eligible_count=good.eligible_count,
        positive_count=good.positive_count,
        negative_count=good.negative_count + 1,
        breakeven_count=good.breakeven_count,
        unavailable_count=good.unavailable_count,
    )
    with pytest.raises(InvestigationInputInvalidError):
        build_failure_context_dataset(tampered, market, indicators)
