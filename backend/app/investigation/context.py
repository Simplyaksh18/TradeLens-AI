"""Phase 4C: deterministic signal-time context & FAILED/NON_FAILED
association engine.

Phase 4A answered "what was the eventual 10-trading-bar outcome
classification of each historical BUY signal?" Phase 4B answered "how did
the eventual return/MAE/MFE distributions differ between FAILED and
NON_FAILED signals?" Phase 4C answers a different question: "what market
and strategy conditions were present AT THE TIME each historical BUY
signal fired, and how were those conditions distributed across the FAILED
versus NON_FAILED populations?"

THE CRITICAL LOOKAHEAD RULE (read before touching this file): a signal's
`classification` (from Phase 4A) is legitimately retrospective -- it is
derived from the FUTURE 10-bar outcome, and that is fine because Phase 4A
already owns that boundary. But every CONTEXT FEATURE this module computes
(regime, realized volatility, RSI14, the two trend-distance fractions) is
computed strictly AT the signal date using only `bars[0..signal_index]`/
`rows[0..signal_index]` -- see `app.audit.engine.build_risk_market_context`,
reused unchanged here specifically because it already enforces that exact
point-in-time cutoff (proven by its own tests). This module must never let
a T+1-or-later value influence a context feature. The future outcome is
used ONLY to look up the already-accepted Phase 4A classification/
population membership -- it never enters a context feature calculation.

Reuse, not duplication: regime and 20-bar annualized realized volatility
are computed by calling the accepted, framework-free Phase 3B
`build_risk_market_context` (app.audit.engine) -- this module does not
reimplement either formula. It does NOT depend on Phase 2B backtesting,
Phase 2C analytics, Phase 3's FastAPI/Pydantic layer, Phase 3's audit
COMPOSER (`build_strategy_audit`/`StrategyAudit`, Phase 3A/3C), or Phase
4B's outcome-summary calculations -- only the narrow, framework-free
Phase 3B risk/regime function.

Structural BUY invariants: `trend_momentum_v1` requires `close > sma20`,
`sma20 > sma50`, and `40 <= rsi14 <= 70` at signal time (see CLAUDE.md's
Current Approved Quantitative Decisions). Every observation this module
processes is, by Phase 4A's own contract, an already-accepted historical
BUY signal -- so its signal-time context MUST satisfy those conditions
(equivalently: regime MUST be BULLISH_TREND). A signal whose signal-time
context does NOT satisfy them is a structural inconsistency (upstream
data corruption), never silently downgraded to a different regime,
skipped, or coerced -- see `_build_signal_context`.

Descriptive research only -- see the module-level warning repeated on
`FailureContextDataset`/`SignalContextSummary`: this module produces
deterministic descriptive summaries (means, medians, counts) of signal-
time conditions across two disjoint historical populations. It never
computes correlation, p-values, confidence intervals, statistical
significance, feature importance, or any predictive/causal claim, and
must never be extended to do so without an explicit later Phase 4
sub-phase decision.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date as Date

from app.audit.engine import build_risk_market_context
from app.audit.models import MarketRegime
from app.core.exceptions import InvestigationInputInvalidError, StrategyAuditInputInvalidError
from app.indicators.models import IndicatorSeries
from app.investigation.models import (
    SignalInvestigationClassification,
    SignalInvestigationDataset,
    SignalInvestigationObservation,
)
from app.market_data.models import OHLCVSeries

_NON_FAILED_CLASSIFICATIONS = (
    SignalInvestigationClassification.POSITIVE,
    SignalInvestigationClassification.BREAKEVEN,
)

RSI_LOWER_BOUND = 40.0
RSI_UPPER_BOUND = 70.0


@dataclass(frozen=True)
class SignalFailureContext:
    """Signal-time (point-in-time) context for one historical BUY signal.

    `classification` is copied from Phase 4A verbatim -- it describes the
    FUTURE outcome and is kept here only so a caller can group/filter
    context by population; it is never derived from, or blended with, the
    context features below. Every other field is computed using ONLY
    information available on or before `signal_date` (see module
    docstring). `rsi14`/`close`/`sma20`/`sma50`/the two trend-distance
    fractions are always present (never `None`) -- a valid historical BUY
    signal structurally requires all of them; a missing one is a data
    inconsistency raised as an error during construction, never
    represented here as `None`. `annualized_realized_volatility_20` is the
    ONE field that may legitimately be `None` (fewer than 21 closes of
    history through `signal_date` -- see Phase 3B)."""

    signal_date: Date
    classification: SignalInvestigationClassification
    regime: MarketRegime
    annualized_realized_volatility_20: float | None
    rsi14: float
    close: float
    sma20: float
    sma50: float
    close_above_sma20_fraction: float
    sma20_above_sma50_fraction: float


@dataclass(frozen=True)
class SignalContextSummary:
    """Deterministic descriptive summary of signal-time context for one
    comparison population (FAILED or NON_FAILED).

    DESCRIPTIVE ONLY: this is not a claim that any field here caused,
    predicts, or explains the population's outcome -- see the module
    docstring. `average`/`median` fields are `None` when `count == 0`
    (never a fabricated `0.0`); `volatility_available_count` +
    `volatility_unavailable_count` always equals `count`, and the
    volatility average/median are computed only over the available
    subset (`None` if none are available). Regime counts are exposed for
    completeness even though every valid observation is expected to be
    BULLISH_TREND (see `_build_signal_context`) -- a non-zero
    `bearish_trend_count`/`transitional_count`/`insufficient_data_count`
    should not occur for a validated dataset."""

    count: int
    average_rsi14: float | None
    median_rsi14: float | None
    volatility_available_count: int
    volatility_unavailable_count: int
    average_annualized_realized_volatility_20: float | None
    median_annualized_realized_volatility_20: float | None
    average_close_above_sma20_fraction: float | None
    median_close_above_sma20_fraction: float | None
    average_sma20_above_sma50_fraction: float | None
    median_sma20_above_sma50_fraction: float | None
    bullish_trend_count: int
    bearish_trend_count: int
    transitional_count: int
    insufficient_data_count: int


_EMPTY_CONTEXT_SUMMARY = SignalContextSummary(
    count=0,
    average_rsi14=None,
    median_rsi14=None,
    volatility_available_count=0,
    volatility_unavailable_count=0,
    average_annualized_realized_volatility_20=None,
    median_annualized_realized_volatility_20=None,
    average_close_above_sma20_fraction=None,
    median_close_above_sma20_fraction=None,
    average_sma20_above_sma50_fraction=None,
    median_sma20_above_sma50_fraction=None,
    bullish_trend_count=0,
    bearish_trend_count=0,
    transitional_count=0,
    insufficient_data_count=0,
)


@dataclass(frozen=True)
class FailureContextDataset:
    """Phase 4C result: signal-time context for every Phase 4A
    observation, plus descriptive FAILED vs. NON_FAILED context summaries.

    `observations` contains exactly one `SignalFailureContext` per input
    Phase 4A observation (`len(observations) == total_signal_count`),
    INCLUDING UNAVAILABLE ones (kept for traceability) -- but UNAVAILABLE
    observations are excluded from both `failed`/`non_failed` summaries,
    same exclusion rule as Phase 4B."""

    provider_symbol: str
    interval: str
    strategy_id: str
    strategy_name: str
    observations: tuple[SignalFailureContext, ...]
    total_signal_count: int
    eligible_count: int
    failed_count: int
    non_failed_count: int
    unavailable_count: int
    failed: SignalContextSummary
    non_failed: SignalContextSummary


def build_failure_context_dataset(
    investigation_dataset: SignalInvestigationDataset,
    market_series: OHLCVSeries,
    indicator_series: IndicatorSeries,
) -> FailureContextDataset:
    """Build the Phase 4C context dataset from an accepted Phase 4A
    `SignalInvestigationDataset` plus the accepted `OHLCVSeries`/
    `IndicatorSeries` it was originally derived from.

    Does not mutate any input or reorder observations. Raises
    InvestigationInputInvalidError for: a symbol/interval mismatch between
    `investigation_dataset` and either series; a signal date absent from
    `market_series` (via the reused Phase 3B alignment check); a
    market/indicator series misalignment; a signal-time regime other than
    BULLISH_TREND (a valid historical BUY signal structurally requires
    `close > sma20 > sma50` at signal time); a missing or non-finite
    close/sma20/sma50; a missing RSI14; an RSI14 outside the accepted
    inclusive `[40, 70]` BUY range; or Phase 4A population counts that are
    inconsistent with their own `observations`.
    """
    _validate_context_alignment(investigation_dataset, market_series, indicator_series)

    date_to_index = {bar.date: i for i, bar in enumerate(market_series.bars)}

    observations = tuple(
        _build_signal_context(observation, market_series, indicator_series, date_to_index)
        for observation in investigation_dataset.observations
    )

    failed_observations = tuple(
        o for o in observations if o.classification == SignalInvestigationClassification.NEGATIVE
    )
    non_failed_observations = tuple(o for o in observations if o.classification in _NON_FAILED_CLASSIFICATIONS)

    failed_count = len(failed_observations)
    non_failed_count = len(non_failed_observations)

    if failed_count != investigation_dataset.negative_count:
        raise InvestigationInputInvalidError(
            f"Phase 4A dataset declares negative_count={investigation_dataset.negative_count}, but "
            f"{failed_count} observation(s) are actually classified NEGATIVE."
        )
    if non_failed_count != investigation_dataset.positive_count + investigation_dataset.breakeven_count:
        raise InvestigationInputInvalidError(
            f"Phase 4A dataset declares positive_count={investigation_dataset.positive_count} + "
            f"breakeven_count={investigation_dataset.breakeven_count}, but {non_failed_count} observation(s) are "
            "actually classified POSITIVE or BREAKEVEN."
        )

    eligible_count = failed_count + non_failed_count
    if investigation_dataset.total_signal_count != eligible_count + investigation_dataset.unavailable_count:
        raise InvestigationInputInvalidError(
            f"Phase 4A dataset declares total_signal_count={investigation_dataset.total_signal_count}, but "
            f"eligible_count ({eligible_count}) + unavailable_count ({investigation_dataset.unavailable_count}) = "
            f"{eligible_count + investigation_dataset.unavailable_count}."
        )

    return FailureContextDataset(
        provider_symbol=investigation_dataset.provider_symbol,
        interval=investigation_dataset.interval,
        strategy_id=investigation_dataset.strategy_id,
        strategy_name=investigation_dataset.strategy_name,
        observations=observations,
        total_signal_count=investigation_dataset.total_signal_count,
        eligible_count=eligible_count,
        failed_count=failed_count,
        non_failed_count=non_failed_count,
        unavailable_count=investigation_dataset.unavailable_count,
        failed=_summarize_context(failed_observations),
        non_failed=_summarize_context(non_failed_observations),
    )


def _validate_context_alignment(
    investigation_dataset: SignalInvestigationDataset, market_series: OHLCVSeries, indicator_series: IndicatorSeries
) -> None:
    if investigation_dataset.provider_symbol != market_series.provider_symbol:
        raise InvestigationInputInvalidError(
            f"Symbol mismatch: investigation dataset={investigation_dataset.provider_symbol!r} vs "
            f"market series={market_series.provider_symbol!r}"
        )
    if investigation_dataset.interval != market_series.interval:
        raise InvestigationInputInvalidError(
            f"Interval mismatch: investigation dataset={investigation_dataset.interval!r} vs "
            f"market series={market_series.interval!r}"
        )
    if investigation_dataset.provider_symbol != indicator_series.provider_symbol:
        raise InvestigationInputInvalidError(
            f"Symbol mismatch: investigation dataset={investigation_dataset.provider_symbol!r} vs "
            f"indicator series={indicator_series.provider_symbol!r}"
        )
    if investigation_dataset.interval != indicator_series.interval:
        raise InvestigationInputInvalidError(
            f"Interval mismatch: investigation dataset={investigation_dataset.interval!r} vs "
            f"indicator series={indicator_series.interval!r}"
        )


def _build_signal_context(
    observation: SignalInvestigationObservation,
    market_series: OHLCVSeries,
    indicator_series: IndicatorSeries,
    date_to_index: dict[Date, int],
) -> SignalFailureContext:
    # `build_risk_market_context` independently validates market/indicator
    # series alignment (symbol/interval/length/strict-chronological dates,
    # which also forbids duplicate dates) and that `signal_date` is present
    # -- reused rather than duplicated. Its own point-in-time cutoff
    # (bars[0..audit_index]/rows[0..audit_index]) is exactly what section 1
    # of CLAUDE.md's Phase 4C notes requires for regime/volatility.
    try:
        risk_context = build_risk_market_context(market_series, indicator_series, observation.signal_date)
    except StrategyAuditInputInvalidError as err:
        raise InvestigationInputInvalidError(
            f"Signal-time context for {observation.signal_date} could not be computed: {err}"
        ) from err

    if risk_context.regime != MarketRegime.BULLISH_TREND:
        raise InvestigationInputInvalidError(
            f"Historical BUY signal at {observation.signal_date} has signal-time regime="
            f"{risk_context.regime.value}, not BULLISH_TREND -- a valid Trend + Momentum v1 BUY requires "
            "close > sma20 > sma50 at signal time; this is a structural inconsistency in the supplied data."
        )

    evidence = risk_context.regime_evidence
    close, sma20, sma50 = evidence.close, evidence.sma20, evidence.sma50
    if close is None or sma20 is None or sma50 is None:
        # Structurally unreachable once regime == BULLISH_TREND (Phase 3B's
        # own contract only returns BULLISH_TREND when all three are
        # present) -- checked explicitly rather than assumed.
        raise InvestigationInputInvalidError(
            f"Historical BUY signal at {observation.signal_date} is missing close/sma20/sma50 despite a "
            "BULLISH_TREND regime -- structurally inconsistent Phase 3B result."
        )

    indicator_row = indicator_series.rows[date_to_index[observation.signal_date]]
    rsi14 = indicator_row.rsi14
    if rsi14 is None:
        raise InvestigationInputInvalidError(
            f"Historical BUY signal at {observation.signal_date} is missing RSI14 -- a valid BUY requires "
            f"{RSI_LOWER_BOUND} <= RSI14 <= {RSI_UPPER_BOUND}."
        )
    if not (RSI_LOWER_BOUND <= rsi14 <= RSI_UPPER_BOUND):
        raise InvestigationInputInvalidError(
            f"Historical BUY signal at {observation.signal_date} has RSI14={rsi14!r}, outside the accepted "
            f"inclusive [{RSI_LOWER_BOUND}, {RSI_UPPER_BOUND}] BUY range -- structural inconsistency."
        )

    return SignalFailureContext(
        signal_date=observation.signal_date,
        classification=observation.classification,
        regime=risk_context.regime,
        annualized_realized_volatility_20=risk_context.annualized_realized_volatility_20,
        rsi14=rsi14,
        close=close,
        sma20=sma20,
        sma50=sma50,
        close_above_sma20_fraction=close / sma20 - 1,
        sma20_above_sma50_fraction=sma20 / sma50 - 1,
    )


def _summarize_context(observations: tuple[SignalFailureContext, ...]) -> SignalContextSummary:
    if not observations:
        return _EMPTY_CONTEXT_SUMMARY

    rsi_values = [o.rsi14 for o in observations]
    close_fractions = [o.close_above_sma20_fraction for o in observations]
    sma_fractions = [o.sma20_above_sma50_fraction for o in observations]
    volatilities = [
        o.annualized_realized_volatility_20 for o in observations if o.annualized_realized_volatility_20 is not None
    ]
    volatility_available_count = len(volatilities)
    volatility_unavailable_count = len(observations) - volatility_available_count

    return SignalContextSummary(
        count=len(observations),
        average_rsi14=sum(rsi_values) / len(rsi_values),
        median_rsi14=statistics.median(rsi_values),
        volatility_available_count=volatility_available_count,
        volatility_unavailable_count=volatility_unavailable_count,
        average_annualized_realized_volatility_20=(sum(volatilities) / len(volatilities)) if volatilities else None,
        median_annualized_realized_volatility_20=statistics.median(volatilities) if volatilities else None,
        average_close_above_sma20_fraction=sum(close_fractions) / len(close_fractions),
        median_close_above_sma20_fraction=statistics.median(close_fractions),
        average_sma20_above_sma50_fraction=sum(sma_fractions) / len(sma_fractions),
        median_sma20_above_sma50_fraction=statistics.median(sma_fractions),
        bullish_trend_count=sum(1 for o in observations if o.regime == MarketRegime.BULLISH_TREND),
        bearish_trend_count=sum(1 for o in observations if o.regime == MarketRegime.BEARISH_TREND),
        transitional_count=sum(1 for o in observations if o.regime == MarketRegime.TRANSITIONAL),
        insufficient_data_count=sum(1 for o in observations if o.regime == MarketRegime.INSUFFICIENT_DATA),
    )
