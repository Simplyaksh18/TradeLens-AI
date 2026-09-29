"""Phase 3A domain model: deterministic point-in-time strategy audit evidence.

Answers, for one `audit_date`: what did the strategy decide and why; what
"Prior Strategy Signals" (frozen V1 term — never "similar"/"matching"/
"analogous"/"comparable market conditions") existed before that date for
this symbol+strategy; which of THOSE signals' +5D/+10D outcomes were
actually knowable as of audit_date; the resulting point-in-time hit rates
and average returns; and, separately, the retrospective (hindsight)
outcome of the audit-date signal itself if it was a BUY.

"Prior Strategy Signal" (V1, frozen): same symbol + same strategy +
decision == BUY + signal_date < audit_date. No feature similarity, KNN,
clustering, regime/volatility matching, or threshold-based "comparable
conditions" exists in V1 — those require an explicit later decision.

This package FILTERS AND AGGREGATES already-accepted Phase 1D
(`StrategyEvaluation`) and Phase 2A (`SignalOutcome`) results — it never
reimplements a strategy rule or a forward-return/MAE/MFE engine, and never
uses Phase 2B portfolio execution to decide what counts as a prior signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from enum import Enum

from app.outcomes.models import SignalOutcome
from app.strategies.models import StrategyEvaluation


@dataclass(frozen=True)
class AuditHorizonStatistics:
    """Point-in-time statistics for one forward horizon (5-bar or 10-bar),
    computed ONLY from prior signals whose outcome was actually knowable as
    of the audit date (see `engine.py`'s eligibility rule).

    Classification is exact/strict — no epsilon: positive means
    `forward_return > 0`, negative means `< 0`, breakeven means `== 0`.
    Breakeven observations stay in the `hit_rate` denominator (they are
    still an eligible observation, just neither a win nor a loss).
    `hit_rate`/`average_return` are `None` when `eligible_outcome_count`
    is 0 -- never fabricated as 0.0.
    """

    eligible_outcome_count: int
    positive_count: int
    negative_count: int
    breakeven_count: int
    hit_rate: float | None
    average_return: float | None


@dataclass(frozen=True)
class HistoricalSignalEvidence:
    """`prior_signal_count` is ALL prior BUY signals before audit_date,
    regardless of whether their forward outcomes were knowable yet — so it
    is valid (expected) for
    `prior_signal_count >= five_bar.eligible_outcome_count >=
    ten_bar.eligible_outcome_count`, never assumed equal.
    """

    prior_signal_count: int
    five_bar: AuditHorizonStatistics
    ten_bar: AuditHorizonStatistics


@dataclass(frozen=True)
class StrategyAuditEvidence:
    """`evaluation` is the Phase 1D `StrategyEvaluation` for audit_date,
    reused verbatim (never re-evaluated). `retrospective_outcome` is the
    Phase 2A `SignalOutcome` for audit_date, reused verbatim, ONLY when
    `evaluation.decision == BUY` -- otherwise `None` (Phase 2A only ever
    creates outcomes for BUY). This is deliberately hindsight and is NEVER
    included in `historical_evidence`'s point-in-time statistics.
    """

    provider_symbol: str
    interval: str
    strategy_id: str
    strategy_name: str
    audit_date: Date
    evaluation: StrategyEvaluation
    historical_evidence: HistoricalSignalEvidence
    retrospective_outcome: SignalOutcome | None


# ---------------------------------------------------------------------------
# Phase 3B: deterministic point-in-time risk context & market regime.
#
# Deliberately NOT merged into StrategyAuditEvidence -- that composition is
# Phase 3C's job. This is context, not another trading signal: it never
# duplicates the Phase 1D strategy evaluation, and encodes no UI strings or
# colors -- `Comparison`/`MarketRegime` are plain domain enums a later UI
# layer maps to presentation, not presentation itself.
# ---------------------------------------------------------------------------


class Comparison(str, Enum):
    ABOVE = "ABOVE"
    BELOW = "BELOW"
    EQUAL = "EQUAL"


class MarketRegime(str, Enum):
    BULLISH_TREND = "BULLISH_TREND"
    BEARISH_TREND = "BEARISH_TREND"
    TRANSITIONAL = "TRANSITIONAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class RegimeEvidence:
    """Raw values + explicit comparison outcomes behind the `MarketRegime`
    classification. `close`/`sma20`/`sma50` and the two comparisons are all
    `None` together only when a required value was unavailable (legitimate
    indicator warm-up, not an error) -- see `MarketRegime.INSUFFICIENT_DATA`.
    """

    close: float | None
    sma20: float | None
    sma50: float | None
    close_vs_sma20: Comparison | None
    sma20_vs_sma50: Comparison | None


@dataclass(frozen=True)
class RiskMarketContext:
    """`annualized_realized_volatility_20` is `None` only when fewer than
    21 raw closes exist through `audit_date` (insufficient history) --
    never fabricated as `0.0`; an actually-zero-variance 20-bar window
    legitimately produces `0.0`, and that is a distinct, valid result.
    """

    provider_symbol: str
    interval: str
    audit_date: Date
    annualized_realized_volatility_20: float | None
    regime: MarketRegime
    regime_evidence: RegimeEvidence


# ---------------------------------------------------------------------------
# Phase 3C: composes the accepted 3A/3B/2A sections into one Strategy Audit.
# Never recalculates them -- only aggregates (HistoricalSignalRisk) and
# composes (StrategyAudit). Deliberately does NOT couple to Phase 2B
# backtesting or Phase 2C analytics: this audits strategy SIGNALS, not
# portfolio execution.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HistoricalSignalRisk:
    """MAE/MFE aggregated over the SAME prior 10-bar-eligible population as
    `HistoricalSignalEvidence.ten_bar` (identical point-in-time eligibility
    rule, shared helper -- see engine.py) -- so
    `eligible_outcome_count == historical_evidence.ten_bar.eligible_outcome_count`
    is a structural invariant, not a coincidence.

    Values are signed decimal fractions, taken verbatim from accepted
    Phase 2A `mae_10d`/`mfe_10d` -- never `abs()`'d, multiplied by 100, or
    rounded. `None` fields (all four) only when `eligible_outcome_count`
    is 0 -- never fabricated as `0.0`.
    """

    eligible_outcome_count: int
    average_mae_10d: float | None
    worst_mae_10d: float | None
    average_mfe_10d: float | None
    best_mfe_10d: float | None


@dataclass(frozen=True)
class StrategyAudit:
    """The composed Phase 3C Strategy Audit for one `audit_date`. Composes
    accepted domain objects wholesale (never flattens/duplicates their
    fields): `evaluation` and `historical_evidence` come from Phase 3A's
    `StrategyAuditEvidence` unchanged; `risk_market_context` comes from
    Phase 3B's `RiskMarketContext` unchanged; `retrospective_outcome`
    (hindsight) stays structurally separate from every point-in-time
    section, exactly as in Phase 3A.
    """

    provider_symbol: str
    interval: str
    strategy_id: str
    strategy_name: str
    audit_date: Date
    evaluation: StrategyEvaluation
    historical_evidence: HistoricalSignalEvidence
    historical_signal_risk: HistoricalSignalRisk
    risk_market_context: RiskMarketContext
    retrospective_outcome: SignalOutcome | None
