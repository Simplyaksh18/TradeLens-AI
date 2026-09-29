"""Phase 4G: cross-layer integration/acceptance tests for the complete
Phase 4 pipeline (2A -> 4A -> 4B -> 4C -> 4D -> 4E schema serialization).

This file deliberately does NOT re-test what Phase 4A/4B/4C/4D/4E's own
accepted suites already cover in isolation (population/median/no-abs()/
no-*100/error-handling/etc. -- see their respective test files). It adds
a small number of STRONG cross-layer checks proving the complete chain is
coherent end-to-end, using one deterministic fixture built by really
calling `evaluate_strategy` (Phase 1D) and `compute_signal_outcomes`
(Phase 2A) -- never a hand-faked SignalOutcomeSeries -- so this is a
genuine 2A-through-4E run, not a re-verification of any single phase.

No network. Run via the normal `pytest` suite.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.indicators.models import IndicatorRow, IndicatorSeries
from app.api.schemas.investigations import StrategyFailureInvestigationResponse
from app.investigation.comparison import build_failure_population_comparison
from app.investigation.composer import build_strategy_failure_investigation
from app.investigation.context import build_failure_context_dataset
from app.investigation.engine import build_signal_investigation_dataset
from app.investigation.models import SignalInvestigationClassification
from app.market_data.models import OHLCVBar, OHLCVSeries
from app.outcomes.engine import compute_signal_outcomes
from app.strategies.engine import evaluate_strategy

SYMBOL = "RELIANCE.NS"
INTERVAL = "1d"
N_BARS = 60
BASE_DATE = date(2024, 1, 1)

BREAKEVEN_INDEX = 30
ISOLATION_INDEX = 5


def _build_closes() -> list[float]:
    closes: list[float] = []
    price = 1000.0
    for i in range(N_BARS):
        cycle_pos = i % 40
        if cycle_pos < 20:
            price += 3.0
        else:
            price -= 3.0
        closes.append(price)
    closes[BREAKEVEN_INDEX + 10] = closes[BREAKEVEN_INDEX]
    return closes


def _market(closes: list[float]) -> OHLCVSeries:
    bars = tuple(
        OHLCVBar(
            date=BASE_DATE + timedelta(days=i),
            open=c,
            high=c + 5,
            low=c - 5,
            close=c,
            adj_close=c,
            volume=1000,
        )
        for i, c in enumerate(closes)
    )
    return OHLCVSeries(provider_symbol=SYMBOL, interval=INTERVAL, bars=bars)


def _indicators(closes: list[float]) -> IndicatorSeries:
    rows = tuple(
        IndicatorRow(
            date=BASE_DATE + timedelta(days=i),
            sma20=c - 10.0,
            sma50=c - 20.0,
            rsi14=55.0,
            average_volume=None,
            volume_ratio=None,
        )
        for i, c in enumerate(closes)
    )
    return IndicatorSeries(provider_symbol=SYMBOL, interval=INTERVAL, rows=rows)


def _run_full_pipeline(closes: list[float]):
    market = _market(closes)
    indicators = _indicators(closes)
    evaluation_series = evaluate_strategy(market, indicators)
    outcome_series = compute_signal_outcomes(market, evaluation_series)
    investigation_dataset = build_signal_investigation_dataset(outcome_series)
    outcome_comparison = build_failure_population_comparison(investigation_dataset)
    context_analysis = build_failure_context_dataset(investigation_dataset, market, indicators)
    investigation = build_strategy_failure_investigation(
        investigation_dataset, outcome_comparison, context_analysis
    )
    response = StrategyFailureInvestigationResponse.from_domain(investigation)
    return {
        "market": market,
        "indicators": indicators,
        "evaluation_series": evaluation_series,
        "outcome_series": outcome_series,
        "investigation_dataset": investigation_dataset,
        "outcome_comparison": outcome_comparison,
        "context_analysis": context_analysis,
        "investigation": investigation,
        "response": response,
    }


def test_fixture_contains_all_four_classifications():
    stages = _run_full_pipeline(_build_closes())
    classifications = {o.classification for o in stages["investigation_dataset"].observations}
    assert classifications == {
        SignalInvestigationClassification.POSITIVE,
        SignalInvestigationClassification.NEGATIVE,
        SignalInvestigationClassification.BREAKEVEN,
        SignalInvestigationClassification.UNAVAILABLE,
    }
    assert stages["investigation_dataset"].negative_count >= 2
    assert (
        stages["investigation_dataset"].positive_count + stages["investigation_dataset"].breakeven_count
    ) >= 2
    assert stages["investigation_dataset"].unavailable_count >= 2


def test_population_invariants_hold_through_full_pipeline():
    stages = _run_full_pipeline(_build_closes())
    dataset = stages["investigation_dataset"]
    investigation = stages["investigation"]
    response = stages["response"]

    for obj in (dataset, investigation, response):
        assert obj.total_signal_count == (
            dataset.positive_count + dataset.negative_count + dataset.breakeven_count + dataset.unavailable_count
        )
        assert obj.eligible_count == dataset.positive_count + dataset.negative_count + dataset.breakeven_count
        assert obj.total_signal_count == obj.eligible_count + obj.unavailable_count

    for obj in (investigation, response):
        assert obj.failed_count == dataset.negative_count
        assert obj.non_failed_count == dataset.positive_count + dataset.breakeven_count

    assert stages["outcome_comparison"].failed.count == dataset.negative_count
    assert stages["outcome_comparison"].non_failed.count == dataset.positive_count + dataset.breakeven_count
    assert stages["context_analysis"].failed.count == dataset.negative_count
    assert stages["context_analysis"].non_failed.count == dataset.positive_count + dataset.breakeven_count


def test_observation_traceability_through_full_pipeline():
    stages = _run_full_pipeline(_build_closes())
    dataset_seq = [(o.signal_date, o.classification) for o in stages["investigation_dataset"].observations]
    context_seq = [(o.signal_date, o.classification) for o in stages["context_analysis"].observations]
    response_seq = [(o.signal_date, o.classification) for o in stages["response"].context_analysis.observations]

    assert dataset_seq == context_seq
    assert [(d, c.value) for d, c in dataset_seq] == response_seq
    assert len(dataset_seq) == stages["investigation_dataset"].total_signal_count


def test_breakeven_signal_present_correctly_classified_and_in_non_failed():
    stages = _run_full_pipeline(_build_closes())
    target_date = BASE_DATE + timedelta(days=BREAKEVEN_INDEX)
    obs = next(o for o in stages["investigation_dataset"].observations if o.signal_date == target_date)
    assert obs.classification == SignalInvestigationClassification.BREAKEVEN
    assert obs.forward_return_10d == 0.0
    assert stages["investigation_dataset"].breakeven_count >= 1
    ctx_obs = next(o for o in stages["context_analysis"].observations if o.signal_date == target_date)
    assert ctx_obs.classification == SignalInvestigationClassification.BREAKEVEN


def test_outcome_values_survive_4d_to_4e_unchanged():
    stages = _run_full_pipeline(_build_closes())
    comparison = stages["outcome_comparison"]
    resp = stages["response"].outcome_comparison
    for pop, resp_pop in ((comparison.failed, resp.failed), (comparison.non_failed, resp.non_failed)):
        assert resp_pop.count == pop.count
        assert resp_pop.average_forward_return_10d == pop.average_forward_return_10d
        assert resp_pop.median_forward_return_10d == pop.median_forward_return_10d
        assert resp_pop.average_mae_10d == pop.average_mae_10d
        assert resp_pop.median_mae_10d == pop.median_mae_10d
        assert resp_pop.worst_mae_10d == pop.worst_mae_10d
        assert resp_pop.average_mfe_10d == pop.average_mfe_10d
        assert resp_pop.median_mfe_10d == pop.median_mfe_10d
        assert resp_pop.best_mfe_10d == pop.best_mfe_10d


def test_context_values_survive_4d_to_4e_unchanged():
    stages = _run_full_pipeline(_build_closes())
    context = stages["context_analysis"]
    resp = stages["response"].context_analysis
    for pop, resp_pop in ((context.failed, resp.failed), (context.non_failed, resp.non_failed)):
        assert resp_pop.count == pop.count
        assert resp_pop.average_rsi14 == pop.average_rsi14
        assert resp_pop.median_rsi14 == pop.median_rsi14
        assert resp_pop.average_annualized_realized_volatility_20 == pop.average_annualized_realized_volatility_20
        assert resp_pop.median_annualized_realized_volatility_20 == pop.median_annualized_realized_volatility_20
        assert resp_pop.average_close_above_sma20_fraction == pop.average_close_above_sma20_fraction
        assert resp_pop.median_close_above_sma20_fraction == pop.median_close_above_sma20_fraction
        assert resp_pop.average_sma20_above_sma50_fraction == pop.average_sma20_above_sma50_fraction
        assert resp_pop.median_sma20_above_sma50_fraction == pop.median_sma20_above_sma50_fraction
        assert resp_pop.bullish_trend_count == pop.bullish_trend_count
        assert resp_pop.bearish_trend_count == pop.bearish_trend_count
        assert resp_pop.transitional_count == pop.transitional_count
        assert resp_pop.insufficient_data_count == pop.insufficient_data_count


def test_near_end_censoring_survives_full_pipeline():
    stages = _run_full_pipeline(_build_closes())
    dataset = stages["investigation_dataset"]
    unavailable_dates = {
        o.signal_date for o in dataset.observations if o.classification == SignalInvestigationClassification.UNAVAILABLE
    }
    assert len(unavailable_dates) > 0

    resp = stages["response"]
    resp_unavailable = {
        o.signal_date
        for o in resp.context_analysis.observations
        if o.classification == "UNAVAILABLE"
    }
    assert unavailable_dates == resp_unavailable
    assert resp.unavailable_count == len(unavailable_dates)
    assert resp.total_signal_count == resp.eligible_count + resp.unavailable_count
    assert resp.eligible_count == resp.failed_count + resp.non_failed_count


def test_point_in_time_isolation_mutating_data_after_signal_date():
    original_closes = _build_closes()
    target_date = BASE_DATE + timedelta(days=ISOLATION_INDEX)

    mutated_closes = list(original_closes)
    for i in range(ISOLATION_INDEX + 1, N_BARS):
        mutated_closes[i] = mutated_closes[i] + 500.0

    original = _run_full_pipeline(original_closes)
    mutated = _run_full_pipeline(mutated_closes)

    def context_for(stage, d):
        return next(o for o in stage["response"].context_analysis.observations if o.signal_date == d)

    ctx_orig = context_for(original, target_date)
    ctx_mut = context_for(mutated, target_date)

    assert ctx_orig.regime == ctx_mut.regime
    assert ctx_orig.rsi14 == ctx_mut.rsi14
    assert ctx_orig.close == ctx_mut.close
    assert ctx_orig.sma20 == ctx_mut.sma20
    assert ctx_orig.sma50 == ctx_mut.sma50
    assert ctx_orig.annualized_realized_volatility_20 == ctx_mut.annualized_realized_volatility_20
    assert ctx_orig.close_above_sma20_fraction == ctx_mut.close_above_sma20_fraction
    assert ctx_orig.sma20_above_sma50_fraction == ctx_mut.sma20_above_sma50_fraction

    assert ctx_orig.classification is not None and ctx_mut.classification is not None


def test_composer_never_recomputes_reference_identity_preserved():
    stages = _run_full_pipeline(_build_closes())
    assert stages["investigation"].outcome_comparison is stages["outcome_comparison"]
    assert stages["investigation"].context_analysis is stages["context_analysis"]


def test_deterministic_repeated_full_pipeline_execution():
    closes = _build_closes()
    first = _run_full_pipeline(closes)["response"]
    second = _run_full_pipeline(closes)["response"]
    assert first == second
