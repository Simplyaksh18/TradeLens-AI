"""Phase 4E API representation of the accepted Phase 4D
`StrategyFailureInvestigation`.

Pure serialization -- no calculation, no new classification/population/
mean/median/MAE-MFE/RSI/SMA/volatility/regime logic. Mirrors the accepted
Phase 4A/4B/4C/4D field names exactly (never renamed for
"frontend-friendliness"). `outcome_comparison` (Phase 4B, retrospective)
and `context_analysis` (Phase 4C, point-in-time) stay distinct response
sections, never merged into one ambiguous "features"/"analysis" object.
"""

from __future__ import annotations

from datetime import date as Date
from typing import Optional

from pydantic import BaseModel

from app.investigation.comparison import FailurePopulationComparison, PopulationSummary
from app.investigation.composer import StrategyFailureInvestigation
from app.investigation.context import FailureContextDataset, SignalContextSummary, SignalFailureContext


class PopulationSummarySchema(BaseModel):
    count: int
    average_forward_return_10d: Optional[float]
    median_forward_return_10d: Optional[float]
    average_mae_10d: Optional[float]
    median_mae_10d: Optional[float]
    worst_mae_10d: Optional[float]
    average_mfe_10d: Optional[float]
    median_mfe_10d: Optional[float]
    best_mfe_10d: Optional[float]

    @classmethod
    def from_domain(cls, summary: PopulationSummary) -> "PopulationSummarySchema":
        return cls(
            count=summary.count,
            average_forward_return_10d=summary.average_forward_return_10d,
            median_forward_return_10d=summary.median_forward_return_10d,
            average_mae_10d=summary.average_mae_10d,
            median_mae_10d=summary.median_mae_10d,
            worst_mae_10d=summary.worst_mae_10d,
            average_mfe_10d=summary.average_mfe_10d,
            median_mfe_10d=summary.median_mfe_10d,
            best_mfe_10d=summary.best_mfe_10d,
        )


class FailurePopulationComparisonSchema(BaseModel):
    failed: PopulationSummarySchema
    non_failed: PopulationSummarySchema

    @classmethod
    def from_domain(cls, comparison: FailurePopulationComparison) -> "FailurePopulationComparisonSchema":
        return cls(
            failed=PopulationSummarySchema.from_domain(comparison.failed),
            non_failed=PopulationSummarySchema.from_domain(comparison.non_failed),
        )


class SignalContextSummarySchema(BaseModel):
    count: int
    average_rsi14: Optional[float]
    median_rsi14: Optional[float]
    volatility_available_count: int
    volatility_unavailable_count: int
    average_annualized_realized_volatility_20: Optional[float]
    median_annualized_realized_volatility_20: Optional[float]
    average_close_above_sma20_fraction: Optional[float]
    median_close_above_sma20_fraction: Optional[float]
    average_sma20_above_sma50_fraction: Optional[float]
    median_sma20_above_sma50_fraction: Optional[float]
    bullish_trend_count: int
    bearish_trend_count: int
    transitional_count: int
    insufficient_data_count: int

    @classmethod
    def from_domain(cls, summary: SignalContextSummary) -> "SignalContextSummarySchema":
        return cls(
            count=summary.count,
            average_rsi14=summary.average_rsi14,
            median_rsi14=summary.median_rsi14,
            volatility_available_count=summary.volatility_available_count,
            volatility_unavailable_count=summary.volatility_unavailable_count,
            average_annualized_realized_volatility_20=summary.average_annualized_realized_volatility_20,
            median_annualized_realized_volatility_20=summary.median_annualized_realized_volatility_20,
            average_close_above_sma20_fraction=summary.average_close_above_sma20_fraction,
            median_close_above_sma20_fraction=summary.median_close_above_sma20_fraction,
            average_sma20_above_sma50_fraction=summary.average_sma20_above_sma50_fraction,
            median_sma20_above_sma50_fraction=summary.median_sma20_above_sma50_fraction,
            bullish_trend_count=summary.bullish_trend_count,
            bearish_trend_count=summary.bearish_trend_count,
            transitional_count=summary.transitional_count,
            insufficient_data_count=summary.insufficient_data_count,
        )


class SignalFailureContextSchema(BaseModel):
    signal_date: Date
    classification: str
    regime: str
    annualized_realized_volatility_20: Optional[float]
    rsi14: float
    close: float
    sma20: float
    sma50: float
    close_above_sma20_fraction: float
    sma20_above_sma50_fraction: float

    @classmethod
    def from_domain(cls, context: SignalFailureContext) -> "SignalFailureContextSchema":
        return cls(
            signal_date=context.signal_date,
            classification=context.classification.value,
            regime=context.regime.value,
            annualized_realized_volatility_20=context.annualized_realized_volatility_20,
            rsi14=context.rsi14,
            close=context.close,
            sma20=context.sma20,
            sma50=context.sma50,
            close_above_sma20_fraction=context.close_above_sma20_fraction,
            sma20_above_sma50_fraction=context.sma20_above_sma50_fraction,
        )


class FailureContextAnalysisSchema(BaseModel):
    failed: SignalContextSummarySchema
    non_failed: SignalContextSummarySchema
    observations: list[SignalFailureContextSchema]

    @classmethod
    def from_domain(cls, dataset: FailureContextDataset) -> "FailureContextAnalysisSchema":
        return cls(
            failed=SignalContextSummarySchema.from_domain(dataset.failed),
            non_failed=SignalContextSummarySchema.from_domain(dataset.non_failed),
            # Chronological/source order preserved exactly -- never
            # re-sorted, grouped by classification, or filtered here.
            observations=[SignalFailureContextSchema.from_domain(o) for o in dataset.observations],
        )


class StrategyFailureInvestigationResponse(BaseModel):
    provider_symbol: str
    interval: str
    strategy_id: str
    strategy_name: str

    total_signal_count: int
    eligible_count: int
    failed_count: int
    non_failed_count: int
    unavailable_count: int

    outcome_comparison: FailurePopulationComparisonSchema
    context_analysis: FailureContextAnalysisSchema

    @classmethod
    def from_domain(cls, investigation: StrategyFailureInvestigation) -> "StrategyFailureInvestigationResponse":
        return cls(
            provider_symbol=investigation.provider_symbol,
            interval=investigation.interval,
            strategy_id=investigation.strategy_id,
            strategy_name=investigation.strategy_name,
            total_signal_count=investigation.total_signal_count,
            eligible_count=investigation.eligible_count,
            failed_count=investigation.failed_count,
            non_failed_count=investigation.non_failed_count,
            unavailable_count=investigation.unavailable_count,
            outcome_comparison=FailurePopulationComparisonSchema.from_domain(investigation.outcome_comparison),
            context_analysis=FailureContextAnalysisSchema.from_domain(investigation.context_analysis),
        )
