"""Phase 4D: Strategy Failure Investigation composer tests.

Builds a full, realistic Phase 4A -> 4B -> 4C pipeline via the REAL
accepted engines (never hand-faking 4B/4C results) so composed fixtures
stay structurally self-consistent, then tampers with individual pieces
(via `dataclasses.replace`, never touching production code) to exercise
Phase 4D's own cross-phase validation.
"""

from __future__ import annotations

import copy
import dataclasses
from datetime import date, timedelta

import pytest

from app.core.exceptions import InvestigationInputInvalidError
from app.investigation.comparison import build_failure_population_comparison
from app.investigation.composer import build_strategy_failure_investigation
from app.investigation.context import build_failure_context_dataset
from app.investigation.models import SignalInvestigationClassification, SignalInvestigationDataset, SignalInvestigationObservation
from app.indicators.models import IndicatorRow, IndicatorSeries
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
    dates: list[date], rows_spec: list[tuple[float, float, float]], symbol: str = SYMBOL, interval: str = INTERVAL
) -> IndicatorSeries:
    rows = tuple(
        IndicatorRow(date=d, sma20=sma20, sma50=sma50, rsi14=rsi14, average_volume=None, volume_ratio=None)
        for d, (sma20, sma50, rsi14) in zip(dates, rows_spec)
    )
    return IndicatorSeries(provider_symbol=symbol, interval=interval, rows=rows)


def _valid_rows(closes: list[float]) -> list[tuple[float, float, float]]:
    return [(c - 10.0, c - 20.0, 55.0) for c in closes]


def _obs(d: date, classification: SignalInvestigationClassification, forward_return_10d: float = 0.02) -> SignalInvestigationObservation:
    present = classification != UNAVAILABLE
    return SignalInvestigationObservation(
        signal_date=d,
        classification=classification,
        reference_close=100.0,
        forward_close_5d=101.0 if present else None,
        forward_return_5d=0.01 if present else None,
        forward_close_10d=100.0 * (1 + forward_return_10d) if present else None,
        forward_return_10d=forward_return_10d if present else None,
        mae_10d=-0.015 if present else None,
        mfe_10d=0.03 if present else None,
        available_forward_bars=15 if present else 3,
    )


def _investigation_dataset(observations: tuple[SignalInvestigationObservation, ...]) -> SignalInvestigationDataset:
    positive = sum(1 for o in observations if o.classification == POSITIVE)
    negative = sum(1 for o in observations if o.classification == NEGATIVE)
    breakeven = sum(1 for o in observations if o.classification == BREAKEVEN)
    unavailable = sum(1 for o in observations if o.classification == UNAVAILABLE)
    return SignalInvestigationDataset(
        provider_symbol=SYMBOL,
        interval=INTERVAL,
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


def _build_pipeline(observations: tuple[SignalInvestigationObservation, ...]):
    """Builds a full, real Phase 4A -> 4B -> 4C pipeline for the given
    observations, using a shared 30-bar valid-BUY market/indicator
    fixture. Returns (dataset, comparison, context_analysis)."""
    dates = _dates()
    closes = _closes()
    rows = _valid_rows(closes)
    market = _market(dates, closes)
    indicators = _indicators(dates, rows)

    dataset = _investigation_dataset(observations)
    comparison = build_failure_population_comparison(dataset)
    context_analysis = build_failure_context_dataset(dataset, market, indicators)
    return dataset, comparison, context_analysis


def _mixed_pipeline():
    dates = _dates()
    observations = (
        _obs(dates[20], NEGATIVE, forward_return_10d=-0.05),
        _obs(dates[21], NEGATIVE, forward_return_10d=-0.02),
        _obs(dates[22], POSITIVE, forward_return_10d=0.05),
        _obs(dates[23], POSITIVE, forward_return_10d=0.08),
        _obs(dates[24], BREAKEVEN, forward_return_10d=0.0),
        _obs(dates[25], UNAVAILABLE),
    )
    return _build_pipeline(observations)


# ---------------------------------------------------------------------------
# 1-8: happy path
# ---------------------------------------------------------------------------


def test_composes_valid_4a_4b_4c_results():
    dataset, comparison, context_analysis = _mixed_pipeline()
    result = build_strategy_failure_investigation(dataset, comparison, context_analysis)
    assert result is not None


def test_metadata_copied_exactly():
    dataset, comparison, context_analysis = _mixed_pipeline()
    result = build_strategy_failure_investigation(dataset, comparison, context_analysis)
    assert result.provider_symbol == SYMBOL
    assert result.interval == INTERVAL
    assert result.strategy_id == STRATEGY_ID
    assert result.strategy_name == STRATEGY_NAME


def test_population_counts_copied_exactly():
    dataset, comparison, context_analysis = _mixed_pipeline()
    result = build_strategy_failure_investigation(dataset, comparison, context_analysis)
    assert result.total_signal_count == 6
    assert result.failed_count == 2
    assert result.non_failed_count == 3  # 2 POSITIVE + 1 BREAKEVEN
    assert result.unavailable_count == 1
    assert result.eligible_count == 5


def test_outcome_comparison_preserved_exactly_by_identity():
    dataset, comparison, context_analysis = _mixed_pipeline()
    result = build_strategy_failure_investigation(dataset, comparison, context_analysis)
    # Embedded by reference, never copied/recomputed.
    assert result.outcome_comparison is comparison
    assert result.outcome_comparison.failed.average_forward_return_10d == comparison.failed.average_forward_return_10d


def test_context_summaries_preserved_exactly_by_identity():
    dataset, comparison, context_analysis = _mixed_pipeline()
    result = build_strategy_failure_investigation(dataset, comparison, context_analysis)
    assert result.context_analysis is context_analysis
    assert result.context_analysis.failed.average_rsi14 == context_analysis.failed.average_rsi14


def test_per_signal_observation_traceability_preserved():
    dataset, comparison, context_analysis = _mixed_pipeline()
    result = build_strategy_failure_investigation(dataset, comparison, context_analysis)
    assert result.context_analysis.observations == context_analysis.observations
    assert len(result.context_analysis.observations) == 6


def test_breakeven_remains_part_of_non_failed():
    dataset, comparison, context_analysis = _mixed_pipeline()
    result = build_strategy_failure_investigation(dataset, comparison, context_analysis)
    assert result.non_failed_count == dataset.positive_count + dataset.breakeven_count
    assert dataset.breakeven_count == 1


def test_unavailable_counted_but_excluded_from_eligible():
    dataset, comparison, context_analysis = _mixed_pipeline()
    result = build_strategy_failure_investigation(dataset, comparison, context_analysis)
    assert result.unavailable_count == 1
    assert result.eligible_count == result.failed_count + result.non_failed_count
    assert result.total_signal_count == result.eligible_count + result.unavailable_count


# ---------------------------------------------------------------------------
# 9-13: metadata mismatch
# ---------------------------------------------------------------------------


def test_symbol_mismatch_4a_vs_4b_rejected():
    dataset, comparison, context_analysis = _mixed_pipeline()
    tampered_comparison = dataclasses.replace(comparison, provider_symbol="OTHER.NS")
    with pytest.raises(InvestigationInputInvalidError):
        build_strategy_failure_investigation(dataset, tampered_comparison, context_analysis)


def test_symbol_mismatch_4a_vs_4c_rejected():
    dataset, comparison, context_analysis = _mixed_pipeline()
    tampered_context = dataclasses.replace(context_analysis, provider_symbol="OTHER.NS")
    with pytest.raises(InvestigationInputInvalidError):
        build_strategy_failure_investigation(dataset, comparison, tampered_context)


def test_interval_mismatch_rejected():
    dataset, comparison, context_analysis = _mixed_pipeline()
    tampered_comparison = dataclasses.replace(comparison, interval="1wk")
    with pytest.raises(InvestigationInputInvalidError):
        build_strategy_failure_investigation(dataset, tampered_comparison, context_analysis)


def test_strategy_id_mismatch_rejected():
    dataset, comparison, context_analysis = _mixed_pipeline()
    tampered_context = dataclasses.replace(context_analysis, strategy_id="other_strategy")
    with pytest.raises(InvestigationInputInvalidError):
        build_strategy_failure_investigation(dataset, comparison, tampered_context)


def test_strategy_name_mismatch_rejected():
    dataset, comparison, context_analysis = _mixed_pipeline()
    tampered_comparison = dataclasses.replace(comparison, strategy_name="Some Other Strategy")
    with pytest.raises(InvestigationInputInvalidError):
        build_strategy_failure_investigation(dataset, tampered_comparison, context_analysis)


# ---------------------------------------------------------------------------
# 14-20: population mismatch
# ---------------------------------------------------------------------------


def test_4b_failed_count_mismatch_rejected():
    dataset, comparison, context_analysis = _mixed_pipeline()
    tampered_failed = dataclasses.replace(comparison.failed, count=comparison.failed.count + 1)
    tampered_comparison = dataclasses.replace(comparison, failed=tampered_failed)
    with pytest.raises(InvestigationInputInvalidError):
        build_strategy_failure_investigation(dataset, tampered_comparison, context_analysis)


def test_4b_non_failed_count_mismatch_rejected():
    dataset, comparison, context_analysis = _mixed_pipeline()
    tampered_non_failed = dataclasses.replace(comparison.non_failed, count=comparison.non_failed.count + 1)
    tampered_comparison = dataclasses.replace(comparison, non_failed=tampered_non_failed)
    with pytest.raises(InvestigationInputInvalidError):
        build_strategy_failure_investigation(dataset, tampered_comparison, context_analysis)


def test_4c_failed_count_mismatch_rejected():
    dataset, comparison, context_analysis = _mixed_pipeline()
    tampered_context = dataclasses.replace(context_analysis, failed_count=context_analysis.failed_count + 1)
    with pytest.raises(InvestigationInputInvalidError):
        build_strategy_failure_investigation(dataset, comparison, tampered_context)


def test_4c_non_failed_count_mismatch_rejected():
    dataset, comparison, context_analysis = _mixed_pipeline()
    tampered_context = dataclasses.replace(context_analysis, non_failed_count=context_analysis.non_failed_count + 1)
    with pytest.raises(InvestigationInputInvalidError):
        build_strategy_failure_investigation(dataset, comparison, tampered_context)


def test_eligible_count_mismatch_rejected():
    dataset, comparison, context_analysis = _mixed_pipeline()
    tampered_comparison = dataclasses.replace(comparison, eligible_count=comparison.eligible_count + 1)
    with pytest.raises(InvestigationInputInvalidError):
        build_strategy_failure_investigation(dataset, tampered_comparison, context_analysis)


def test_unavailable_count_mismatch_rejected():
    dataset, comparison, context_analysis = _mixed_pipeline()
    tampered_context = dataclasses.replace(context_analysis, unavailable_count=context_analysis.unavailable_count + 1)
    with pytest.raises(InvestigationInputInvalidError):
        build_strategy_failure_investigation(dataset, comparison, tampered_context)


def test_total_signal_count_mismatch_rejected():
    dataset, comparison, context_analysis = _mixed_pipeline()
    tampered_comparison = dataclasses.replace(comparison, total_signal_count=comparison.total_signal_count + 1)
    with pytest.raises(InvestigationInputInvalidError):
        build_strategy_failure_investigation(dataset, tampered_comparison, context_analysis)


# ---------------------------------------------------------------------------
# 21-25: observation alignment
# ---------------------------------------------------------------------------


def test_4c_missing_one_observation_rejected():
    dataset, comparison, context_analysis = _mixed_pipeline()
    tampered_context = dataclasses.replace(context_analysis, observations=context_analysis.observations[:-1])
    with pytest.raises(InvestigationInputInvalidError):
        build_strategy_failure_investigation(dataset, comparison, tampered_context)


def test_4c_extra_observation_rejected():
    dataset, comparison, context_analysis = _mixed_pipeline()
    tampered_context = dataclasses.replace(
        context_analysis, observations=context_analysis.observations + (context_analysis.observations[0],)
    )
    with pytest.raises(InvestigationInputInvalidError):
        build_strategy_failure_investigation(dataset, comparison, tampered_context)


def test_4c_changed_signal_date_rejected():
    dataset, comparison, context_analysis = _mixed_pipeline()
    observations = list(context_analysis.observations)
    observations[0] = dataclasses.replace(observations[0], signal_date=observations[0].signal_date + timedelta(days=1))
    tampered_context = dataclasses.replace(context_analysis, observations=tuple(observations))
    with pytest.raises(InvestigationInputInvalidError):
        build_strategy_failure_investigation(dataset, comparison, tampered_context)


def test_4c_changed_classification_rejected():
    dataset, comparison, context_analysis = _mixed_pipeline()
    observations = list(context_analysis.observations)
    # Flip the first observation's classification to something else.
    new_classification = POSITIVE if observations[0].classification != POSITIVE else NEGATIVE
    observations[0] = dataclasses.replace(observations[0], classification=new_classification)
    tampered_context = dataclasses.replace(context_analysis, observations=tuple(observations))
    with pytest.raises(InvestigationInputInvalidError):
        build_strategy_failure_investigation(dataset, comparison, tampered_context)


def test_4c_reordered_observations_rejected():
    dataset, comparison, context_analysis = _mixed_pipeline()
    reordered = tuple(reversed(context_analysis.observations))
    assert reordered != context_analysis.observations  # sanity: fixture actually has >1 distinct order
    tampered_context = dataclasses.replace(context_analysis, observations=reordered)
    with pytest.raises(InvestigationInputInvalidError):
        build_strategy_failure_investigation(dataset, comparison, tampered_context)


# ---------------------------------------------------------------------------
# 26-29: empty populations
# ---------------------------------------------------------------------------


def test_zero_total_signals():
    dataset, comparison, context_analysis = _build_pipeline(())
    result = build_strategy_failure_investigation(dataset, comparison, context_analysis)
    assert result.total_signal_count == 0
    assert result.eligible_count == 0
    assert result.unavailable_count == 0


def test_zero_failed_signals():
    dates = _dates()
    dataset, comparison, context_analysis = _build_pipeline((_obs(dates[20], POSITIVE),))
    result = build_strategy_failure_investigation(dataset, comparison, context_analysis)
    assert result.failed_count == 0
    assert result.outcome_comparison.failed.count == 0
    assert result.outcome_comparison.failed.average_forward_return_10d is None
    assert result.context_analysis.failed.count == 0
    assert result.context_analysis.failed.average_rsi14 is None


def test_zero_non_failed_signals():
    dates = _dates()
    dataset, comparison, context_analysis = _build_pipeline((_obs(dates[20], NEGATIVE),))
    result = build_strategy_failure_investigation(dataset, comparison, context_analysis)
    assert result.non_failed_count == 0
    assert result.outcome_comparison.non_failed.count == 0
    assert result.context_analysis.non_failed.count == 0


def test_all_unavailable_signals():
    dates = _dates()
    dataset, comparison, context_analysis = _build_pipeline((_obs(dates[20], UNAVAILABLE), _obs(dates[21], UNAVAILABLE)))
    result = build_strategy_failure_investigation(dataset, comparison, context_analysis)
    assert result.total_signal_count == 2
    assert result.unavailable_count == 2
    assert result.eligible_count == 0
    assert result.failed_count == 0
    assert result.non_failed_count == 0
    assert len(result.context_analysis.observations) == 2  # still traceable


# ---------------------------------------------------------------------------
# 30-33: determinism / non-mutation
# ---------------------------------------------------------------------------


def test_deterministic_repeated_build():
    dataset, comparison, context_analysis = _mixed_pipeline()
    first = build_strategy_failure_investigation(dataset, comparison, context_analysis)
    second = build_strategy_failure_investigation(dataset, comparison, context_analysis)
    assert first == second


def test_4a_input_unchanged():
    dataset, comparison, context_analysis = _mixed_pipeline()
    before = copy.deepcopy(dataset)
    build_strategy_failure_investigation(dataset, comparison, context_analysis)
    assert dataset == before


def test_4b_input_unchanged():
    dataset, comparison, context_analysis = _mixed_pipeline()
    before = copy.deepcopy(comparison)
    build_strategy_failure_investigation(dataset, comparison, context_analysis)
    assert comparison == before


def test_4c_input_unchanged():
    dataset, comparison, context_analysis = _mixed_pipeline()
    before = copy.deepcopy(context_analysis)
    build_strategy_failure_investigation(dataset, comparison, context_analysis)
    assert context_analysis == before


# ---------------------------------------------------------------------------
# No recomputation
# ---------------------------------------------------------------------------


def test_no_recomputation_distinctive_values_preserved_unchanged():
    dataset, comparison, context_analysis = _mixed_pipeline()

    # Distinctive, non-rounded values already computed by the real Phase
    # 4B/4C engines -- captured before composition.
    distinctive_avg_return = comparison.failed.average_forward_return_10d
    distinctive_median_mae = comparison.non_failed.median_mae_10d
    distinctive_avg_rsi = context_analysis.failed.average_rsi14
    distinctive_median_vol = context_analysis.non_failed.median_annualized_realized_volatility_20

    result = build_strategy_failure_investigation(dataset, comparison, context_analysis)

    assert result.outcome_comparison.failed.average_forward_return_10d == distinctive_avg_return
    assert result.outcome_comparison.non_failed.median_mae_10d == distinctive_median_mae
    assert result.context_analysis.failed.average_rsi14 == distinctive_avg_rsi
    assert result.context_analysis.non_failed.median_annualized_realized_volatility_20 == distinctive_median_vol

    # Strongest possible proof of "no recomputation": the nested accepted
    # objects are embedded by reference, not copied/rebuilt.
    assert result.outcome_comparison is comparison
    assert result.context_analysis is context_analysis
