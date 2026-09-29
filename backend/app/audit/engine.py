"""Phase 3A: deterministic point-in-time strategy audit evidence engine.

Point-in-time eligibility rule (critical, see CLAUDE.md Phase 3A): a prior
BUY signal at bar index `i` merely occurring before `audit_date` does NOT
mean its forward outcome was knowable on `audit_date`. The 5-bar outcome
is eligible for historical statistics only when the 5th forward trading
bar's date is on or before `audit_date` -- i.e. `i + 5 <= audit_index`,
where `audit_index` is audit_date's own position in the aligned series.
10-bar uses `i + 10 <= audit_index`. This is pure trading-bar INDEX
arithmetic (never calendar-day math, never `available_forward_bars`,
which reflects total series length, not audit-relative knowability).

The audit-date signal itself is never part of the prior-signal population.
Signals after audit_date are never considered (prior signals are found by
scanning indices `0..audit_index-1` only) -- so changing bars strictly
after audit_date can only ever affect the audit-date signal's own
*retrospective* (hindsight) outcome, never `historical_evidence`.
"""

from __future__ import annotations

import statistics
from datetime import date as Date
from math import isfinite, sqrt

from app.audit.models import (
    AuditHorizonStatistics,
    Comparison,
    HistoricalSignalEvidence,
    HistoricalSignalRisk,
    MarketRegime,
    RegimeEvidence,
    RiskMarketContext,
    StrategyAudit,
    StrategyAuditEvidence,
)
from app.core.exceptions import StrategyAuditInputInvalidError
from app.indicators.models import IndicatorRow, IndicatorSeries
from app.market_data.models import OHLCVBar, OHLCVSeries
from app.outcomes.models import SignalOutcome, SignalOutcomeSeries
from app.strategies.models import StrategyDecision, StrategyEvaluation, StrategyEvaluationSeries

FIVE_BAR = 5
TEN_BAR = 10
VOLATILITY_WINDOW_BARS = 20  # 20 returns -> 21 closes
TRADING_PERIODS_PER_YEAR = 252  # V1 convention; valid only for interval "1d".


def build_strategy_audit_evidence(
    market_series: OHLCVSeries,
    evaluation_series: StrategyEvaluationSeries,
    outcome_series: SignalOutcomeSeries,
    audit_date: Date,
    evidence_start_date: Date | None = None,
) -> StrategyAuditEvidence:
    """Build Phase 3A audit evidence for `audit_date`.

    `evidence_start_date` (optional, default `None` = no lower bound,
    i.e. the original unrestricted behavior) separates CALCULATION history
    from the requested HISTORICAL EVIDENCE POPULATION (see CLAUDE.md Phase
    3D's calculation-history-vs-evidence-window correction): when given, a
    prior BUY only counts toward `prior_signal_count`/5D/10D statistics if
    `signal_date >= evidence_start_date`. `market_series`/`evaluation_series`
    may still legitimately contain bars BEFORE `evidence_start_date` --
    those exist only to give the strategy/indicator engines enough warm-up
    history to evaluate `audit_date` correctly, and must never leak into
    the evidence population. This never changes `audit_date`'s own
    `evaluation` or the alignment/censoring rules -- only which PRIOR
    signals are counted.

    Raises StrategyAuditInputInvalidError for structural misalignment, a
    missing `audit_date`, an outcome that can't be matched to a BUY
    evaluation, or a structurally inconsistent/non-finite forward return
    on a point-in-time-eligible outcome. Never mutates its inputs.
    """
    _validate_alignment(market_series, evaluation_series, outcome_series)

    bars = market_series.bars
    evaluations = evaluation_series.evaluations
    outcome_by_date = {o.date: o for o in outcome_series.outcomes}
    _validate_outcomes_match_buy_evaluations(evaluations, outcome_by_date)

    date_to_index = {bar.date: i for i, bar in enumerate(bars)}
    audit_index = date_to_index.get(audit_date)
    if audit_index is None:
        raise StrategyAuditInputInvalidError(f"audit_date {audit_date} is not present in the aligned series")

    evidence_start_index = _resolve_evidence_start_index(bars, evidence_start_date)
    audit_evaluation = evaluations[audit_index]

    five_bar_returns: list[float] = []
    ten_bar_returns: list[float] = []
    prior_signal_count = 0

    for i, evaluation, outcome in _iter_prior_buy_signals(evaluations, outcome_by_date, audit_index, evidence_start_index):
        prior_signal_count += 1
        if _is_horizon_eligible(i, audit_index, FIVE_BAR):
            five_bar_returns.append(_require_eligible_return(outcome.forward_return_5d, evaluation.date, "5D"))
        if _is_horizon_eligible(i, audit_index, TEN_BAR):
            ten_bar_returns.append(_require_eligible_return(outcome.forward_return_10d, evaluation.date, "10D"))

    retrospective_outcome: SignalOutcome | None = None
    if audit_evaluation.decision == StrategyDecision.BUY:
        retrospective_outcome = outcome_by_date.get(audit_date)
        if retrospective_outcome is None:
            raise StrategyAuditInputInvalidError(f"No Phase 2A outcome found for audit-date BUY signal at {audit_date}")

    return StrategyAuditEvidence(
        provider_symbol=market_series.provider_symbol,
        interval=market_series.interval,
        strategy_id=evaluation_series.strategy_id,
        strategy_name=evaluation_series.strategy_name,
        audit_date=audit_date,
        evaluation=audit_evaluation,
        historical_evidence=HistoricalSignalEvidence(
            prior_signal_count=prior_signal_count,
            five_bar=_build_horizon_statistics(five_bar_returns),
            ten_bar=_build_horizon_statistics(ten_bar_returns),
        ),
        retrospective_outcome=retrospective_outcome,
    )


def _iter_prior_buy_signals(
    evaluations: tuple[StrategyEvaluation, ...],
    outcome_by_date: dict[Date, SignalOutcome],
    audit_index: int,
    start_index: int = 0,
):
    """Yields `(index, evaluation, outcome)` for every prior BUY signal
    with `start_index <= index < audit_index`, raising if any lacks a
    matching Phase 2A outcome. The SINGLE source of truth for "prior
    signal" membership and per-signal outcome lookup, shared by Phase 3A's
    5D/10D historical statistics AND Phase 3C's `HistoricalSignalRisk` --
    they must never independently evolve two subtly different eligibility
    definitions.

    `start_index` (default 0 = no lower bound) implements the requested
    evidence-population boundary (`evidence_start_date`) -- bars before it
    may still exist in `evaluations` (loaded only for calculation warm-up)
    but are structurally excluded from the prior-signal population here.
    """
    for i in range(start_index, audit_index):  # strictly BEFORE audit_date; audit signal itself excluded
        evaluation = evaluations[i]
        if evaluation.decision != StrategyDecision.BUY:
            continue
        outcome = outcome_by_date.get(evaluation.date)
        if outcome is None:
            raise StrategyAuditInputInvalidError(f"No Phase 2A outcome found for prior BUY signal at {evaluation.date}")
        yield i, evaluation, outcome


def _resolve_evidence_start_index(bars: tuple[OHLCVBar, ...], evidence_start_date: Date | None) -> int:
    """First bar index with `date >= evidence_start_date` (a threshold
    comparison, not an exact-bar lookup like `audit_date` -- a
    weekend/holiday `evidence_start_date` is valid and simply rounds
    forward to the next trading bar). `None` means no lower bound."""
    if evidence_start_date is None:
        return 0
    for i, bar in enumerate(bars):
        if bar.date >= evidence_start_date:
            return i
    return len(bars)


def _is_horizon_eligible(i: int, audit_index: int, horizon_bars: int) -> bool:
    """Shared point-in-time eligibility predicate: knowable iff the horizon's
    forward trading bar's index is on or before `audit_index` (inclusive)."""
    return i + horizon_bars <= audit_index


def _require_eligible_return(value: float | None, signal_date: Date, horizon: str) -> float:
    if value is None:
        raise StrategyAuditInputInvalidError(
            f"{horizon} outcome for signal at {signal_date} is point-in-time eligible but missing from the "
            "supplied outcome series (structural inconsistency between market series and outcome series)"
        )
    if not isfinite(value):
        raise StrategyAuditInputInvalidError(f"Non-finite {horizon} forward return for signal at {signal_date}")
    return value


def _build_horizon_statistics(returns: list[float]) -> AuditHorizonStatistics:
    count = len(returns)
    if count == 0:
        return AuditHorizonStatistics(
            eligible_outcome_count=0, positive_count=0, negative_count=0, breakeven_count=0,
            hit_rate=None, average_return=None,
        )
    positive = sum(1 for r in returns if r > 0)
    negative = sum(1 for r in returns if r < 0)
    breakeven = sum(1 for r in returns if r == 0)
    return AuditHorizonStatistics(
        eligible_outcome_count=count,
        positive_count=positive,
        negative_count=negative,
        breakeven_count=breakeven,
        hit_rate=positive / count,
        average_return=sum(returns) / count,
    )


def _validate_alignment(
    market_series: OHLCVSeries, evaluation_series: StrategyEvaluationSeries, outcome_series: SignalOutcomeSeries
) -> None:
    if not (market_series.provider_symbol == evaluation_series.provider_symbol == outcome_series.provider_symbol):
        raise StrategyAuditInputInvalidError(
            f"Symbol mismatch: market={market_series.provider_symbol!r} "
            f"evaluation={evaluation_series.provider_symbol!r} outcome={outcome_series.provider_symbol!r}"
        )
    if not (market_series.interval == evaluation_series.interval == outcome_series.interval):
        raise StrategyAuditInputInvalidError(
            f"Interval mismatch: market={market_series.interval!r} "
            f"evaluation={evaluation_series.interval!r} outcome={outcome_series.interval!r}"
        )
    if evaluation_series.strategy_id != outcome_series.strategy_id:
        raise StrategyAuditInputInvalidError(
            f"Strategy mismatch: evaluation={evaluation_series.strategy_id!r} outcome={outcome_series.strategy_id!r}"
        )
    if len(market_series.bars) != len(evaluation_series.evaluations):
        raise StrategyAuditInputInvalidError(
            f"Row count mismatch: {len(market_series.bars)} market bars vs "
            f"{len(evaluation_series.evaluations)} evaluations"
        )

    previous_date: Date | None = None
    for bar, evaluation in zip(market_series.bars, evaluation_series.evaluations):
        if bar.date != evaluation.date:
            raise StrategyAuditInputInvalidError(f"Date misalignment: market bar date {bar.date} != evaluation date {evaluation.date}")
        if previous_date is not None and bar.date <= previous_date:
            raise StrategyAuditInputInvalidError(f"Market/evaluation rows are not strictly chronological at {bar.date}")
        previous_date = bar.date

    evaluation_dates = {e.date for e in evaluation_series.evaluations}
    seen_outcome_dates: set[Date] = set()
    for outcome in outcome_series.outcomes:
        if outcome.date in seen_outcome_dates:
            raise StrategyAuditInputInvalidError(f"Duplicate outcome date {outcome.date}")
        seen_outcome_dates.add(outcome.date)
        if outcome.date not in evaluation_dates:
            raise StrategyAuditInputInvalidError(f"Outcome date {outcome.date} has no corresponding evaluation")


def _validate_outcomes_match_buy_evaluations(
    evaluations: tuple[StrategyEvaluation, ...], outcome_by_date: dict[Date, SignalOutcome]
) -> None:
    evaluation_by_date = {e.date: e for e in evaluations}
    for date, outcome in outcome_by_date.items():
        evaluation = evaluation_by_date[date]  # presence already guaranteed by _validate_alignment
        if evaluation.decision != StrategyDecision.BUY:
            raise StrategyAuditInputInvalidError(
                f"Outcome at {date} does not correspond to a BUY evaluation (decision={evaluation.decision.value})"
            )


# ---------------------------------------------------------------------------
# Phase 3B: deterministic point-in-time risk context & market regime.
#
# Point-in-time cutoff: both the volatility window and the regime snapshot
# are read ONLY from `bars[0..audit_index]` / `rows[0..audit_index]` -- bars
# strictly after audit_index are never indexed, so they structurally cannot
# affect the result (proven by test, not just by convention).
# ---------------------------------------------------------------------------


def build_risk_market_context(
    market_series: OHLCVSeries, indicator_series: IndicatorSeries, audit_date: Date
) -> RiskMarketContext:
    """Build Phase 3B risk/regime context for `audit_date`.

    Raises StrategyAuditInputInvalidError for structural misalignment, a
    missing `audit_date`, a non-finite raw close, or a non-finite
    (present-but-malformed) SMA value. A legitimately unavailable SMA
    (`None`, indicator warm-up) is NOT an error -- it produces
    `MarketRegime.INSUFFICIENT_DATA`, a normal, valid result. Never
    mutates its inputs.
    """
    _validate_risk_context_alignment(market_series, indicator_series)

    bars = market_series.bars
    date_to_index = {bar.date: i for i, bar in enumerate(bars)}
    audit_index = date_to_index.get(audit_date)
    if audit_index is None:
        raise StrategyAuditInputInvalidError(f"audit_date {audit_date} is not present in the aligned series")

    regime, evidence = _classify_regime(bars[audit_index], indicator_series.rows[audit_index])
    volatility = _compute_annualized_volatility_20(bars, audit_index)

    return RiskMarketContext(
        provider_symbol=market_series.provider_symbol,
        interval=market_series.interval,
        audit_date=audit_date,
        annualized_realized_volatility_20=volatility,
        regime=regime,
        regime_evidence=evidence,
    )


def _classify_regime(bar: OHLCVBar, indicator_row: IndicatorRow) -> tuple[MarketRegime, RegimeEvidence]:
    close = bar.close
    sma20 = indicator_row.sma20
    sma50 = indicator_row.sma50

    if sma20 is None or sma50 is None:
        # Legitimate indicator warm-up -- INSUFFICIENT DATA, not an error.
        return MarketRegime.INSUFFICIENT_DATA, RegimeEvidence(
            close=close, sma20=sma20, sma50=sma50, close_vs_sma20=None, sma20_vs_sma50=None
        )

    close_vs_sma20 = _compare(close, sma20)
    sma20_vs_sma50 = _compare(sma20, sma50)
    evidence = RegimeEvidence(close=close, sma20=sma20, sma50=sma50, close_vs_sma20=close_vs_sma20, sma20_vs_sma50=sma20_vs_sma50)

    if close_vs_sma20 == Comparison.ABOVE and sma20_vs_sma50 == Comparison.ABOVE:
        return MarketRegime.BULLISH_TREND, evidence
    if close_vs_sma20 == Comparison.BELOW and sma20_vs_sma50 == Comparison.BELOW:
        return MarketRegime.BEARISH_TREND, evidence
    return MarketRegime.TRANSITIONAL, evidence


def _compare(a: float, b: float) -> Comparison:
    if a > b:
        return Comparison.ABOVE
    if a < b:
        return Comparison.BELOW
    return Comparison.EQUAL


def _compute_annualized_volatility_20(bars: tuple[OHLCVBar, ...], audit_index: int) -> float | None:
    window_start = audit_index - VOLATILITY_WINDOW_BARS  # 21 closes: window_start..audit_index inclusive
    if window_start < 0:
        return None
    closes = [bars[j].close for j in range(window_start, audit_index + 1)]
    returns = [closes[k] / closes[k - 1] - 1 for k in range(1, len(closes))]
    return statistics.stdev(returns) * sqrt(TRADING_PERIODS_PER_YEAR)


def _validate_risk_context_alignment(market_series: OHLCVSeries, indicator_series: IndicatorSeries) -> None:
    if market_series.provider_symbol != indicator_series.provider_symbol:
        raise StrategyAuditInputInvalidError(
            f"Symbol mismatch: market={market_series.provider_symbol!r} indicator={indicator_series.provider_symbol!r}"
        )
    if market_series.interval != indicator_series.interval:
        raise StrategyAuditInputInvalidError(
            f"Interval mismatch: market={market_series.interval!r} indicator={indicator_series.interval!r}"
        )
    if len(market_series.bars) != len(indicator_series.rows):
        raise StrategyAuditInputInvalidError(
            f"Row count mismatch: {len(market_series.bars)} market bars vs {len(indicator_series.rows)} indicator rows"
        )

    previous_date: Date | None = None
    for bar, row in zip(market_series.bars, indicator_series.rows):
        if bar.date != row.date:
            raise StrategyAuditInputInvalidError(f"Date misalignment: market bar date {bar.date} != indicator row date {row.date}")
        if previous_date is not None and bar.date <= previous_date:
            raise StrategyAuditInputInvalidError(f"Market/indicator rows are not strictly chronological at {bar.date}")
        previous_date = bar.date
        if not isfinite(bar.close):
            raise StrategyAuditInputInvalidError(f"Non-finite raw close at {bar.date}")
        if row.sma20 is not None and not isfinite(row.sma20):
            raise StrategyAuditInputInvalidError(f"Non-finite sma20 at {bar.date}")
        if row.sma50 is not None and not isfinite(row.sma50):
            raise StrategyAuditInputInvalidError(f"Non-finite sma50 at {bar.date}")


# ---------------------------------------------------------------------------
# Phase 3C: composes the accepted 3A/3B sections into one Strategy Audit.
#
# Both sub-builders below validate against the SAME `market_series` object
# and are driven by the SAME single `audit_date` parameter -- so evaluation/
# outcome/indicator data are transitively pinned to one symbol/interval/date
# by construction. No separate "full alignment" re-check is needed (that
# would just duplicate `_validate_alignment`/`_validate_risk_context_alignment`).
# ---------------------------------------------------------------------------


def build_strategy_audit(
    market_series: OHLCVSeries,
    evaluation_series: StrategyEvaluationSeries,
    outcome_series: SignalOutcomeSeries,
    indicator_series: IndicatorSeries,
    audit_date: Date,
    evidence_start_date: Date | None = None,
) -> StrategyAudit:
    """Compose the complete Phase 3C Strategy Audit for `audit_date`.

    `evidence_start_date` (optional; see `build_strategy_audit_evidence`'s
    docstring for the full calculation-history-vs-evidence-population
    contract) bounds `historical_evidence`/`historical_signal_risk` only --
    `evaluation` and `risk_market_context` are computed from `market_series`/
    `indicator_series` as supplied and are NOT affected by it, so callers
    may load extra pre-`evidence_start_date` bars purely for SMA/RSI/
    volatility warm-up without that history leaking into the evidence
    population.

    Delegates to the accepted `build_strategy_audit_evidence` (Phase 3A)
    and `build_risk_market_context` (Phase 3B) unchanged, and adds one new
    aggregation (`HistoricalSignalRisk`) over the identical prior-signal
    10-bar-eligible population Phase 3A already computes (shared
    `_iter_prior_buy_signals`/`_is_horizon_eligible` helpers -- see their
    docstrings). Never couples to Phase 2B backtesting or Phase 2C
    analytics: this audits strategy signals, not portfolio execution.
    """
    audit_evidence = build_strategy_audit_evidence(
        market_series, evaluation_series, outcome_series, audit_date, evidence_start_date
    )
    risk_context = build_risk_market_context(market_series, indicator_series, audit_date)

    date_to_index = {bar.date: i for i, bar in enumerate(market_series.bars)}
    audit_index = date_to_index[audit_date]  # presence already guaranteed by the sub-builders above
    evidence_start_index = _resolve_evidence_start_index(market_series.bars, evidence_start_date)
    outcome_by_date = {o.date: o for o in outcome_series.outcomes}
    historical_signal_risk = _build_historical_signal_risk(
        evaluation_series.evaluations, outcome_by_date, audit_index, evidence_start_index
    )

    return StrategyAudit(
        provider_symbol=market_series.provider_symbol,
        interval=market_series.interval,
        strategy_id=evaluation_series.strategy_id,
        strategy_name=evaluation_series.strategy_name,
        audit_date=audit_date,
        evaluation=audit_evidence.evaluation,
        historical_evidence=audit_evidence.historical_evidence,
        historical_signal_risk=historical_signal_risk,
        risk_market_context=risk_context,
        retrospective_outcome=audit_evidence.retrospective_outcome,
    )


def _build_historical_signal_risk(
    evaluations: tuple[StrategyEvaluation, ...],
    outcome_by_date: dict[Date, SignalOutcome],
    audit_index: int,
    start_index: int = 0,
) -> HistoricalSignalRisk:
    maes: list[float] = []
    mfes: list[float] = []

    for i, evaluation, outcome in _iter_prior_buy_signals(evaluations, outcome_by_date, audit_index, start_index):
        if not _is_horizon_eligible(i, audit_index, TEN_BAR):
            continue
        mae, mfe = outcome.mae_10d, outcome.mfe_10d
        if mae is None or mfe is None:
            raise StrategyAuditInputInvalidError(
                f"10D-eligible outcome at {evaluation.date} is missing mae_10d/mfe_10d "
                "(structural inconsistency between market series and outcome series)"
            )
        if not isfinite(mae) or not isfinite(mfe):
            raise StrategyAuditInputInvalidError(f"Non-finite mae_10d/mfe_10d for signal at {evaluation.date}")
        maes.append(mae)
        mfes.append(mfe)

    count = len(maes)
    if count == 0:
        return HistoricalSignalRisk(
            eligible_outcome_count=0, average_mae_10d=None, worst_mae_10d=None, average_mfe_10d=None, best_mfe_10d=None
        )
    return HistoricalSignalRisk(
        eligible_outcome_count=count,
        average_mae_10d=sum(maes) / count,
        worst_mae_10d=min(maes),
        average_mfe_10d=sum(mfes) / count,
        best_mfe_10d=max(mfes),
    )
