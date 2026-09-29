"""Phase 3D API representation of the accepted Phase 3C `StrategyAudit`.

Pure serialization -- no calculation, no new eligibility/regime/MAE-MFE
logic, no reinterpretation of the domain result. Reuses the existing
Phase 1D `StrategyEvaluationSchema` and Phase 2A `SignalOutcomeSchema`
verbatim for `evaluation`/`retrospective_outcome` rather than duplicating
their field mapping.
"""

from __future__ import annotations

from datetime import date as Date
from typing import Optional

from pydantic import BaseModel

from app.api.schemas.outcomes import SignalOutcomeSchema
from app.api.schemas.strategies import StrategyEvaluationSchema
from app.audit.models import (
    AuditHorizonStatistics,
    HistoricalSignalEvidence,
    HistoricalSignalRisk,
    RegimeEvidence,
    RiskMarketContext,
    StrategyAudit,
)


class AuditHorizonStatisticsSchema(BaseModel):
    eligible_outcome_count: int
    positive_count: int
    negative_count: int
    breakeven_count: int
    hit_rate: Optional[float]
    average_return: Optional[float]

    @classmethod
    def from_domain(cls, stats: AuditHorizonStatistics) -> "AuditHorizonStatisticsSchema":
        return cls(
            eligible_outcome_count=stats.eligible_outcome_count,
            positive_count=stats.positive_count,
            negative_count=stats.negative_count,
            breakeven_count=stats.breakeven_count,
            hit_rate=stats.hit_rate,
            average_return=stats.average_return,
        )


class HistoricalSignalEvidenceSchema(BaseModel):
    prior_signal_count: int
    five_bar: AuditHorizonStatisticsSchema
    ten_bar: AuditHorizonStatisticsSchema

    @classmethod
    def from_domain(cls, evidence: HistoricalSignalEvidence) -> "HistoricalSignalEvidenceSchema":
        return cls(
            prior_signal_count=evidence.prior_signal_count,
            five_bar=AuditHorizonStatisticsSchema.from_domain(evidence.five_bar),
            ten_bar=AuditHorizonStatisticsSchema.from_domain(evidence.ten_bar),
        )


class HistoricalSignalRiskSchema(BaseModel):
    eligible_outcome_count: int
    average_mae_10d: Optional[float]
    worst_mae_10d: Optional[float]
    average_mfe_10d: Optional[float]
    best_mfe_10d: Optional[float]

    @classmethod
    def from_domain(cls, risk: HistoricalSignalRisk) -> "HistoricalSignalRiskSchema":
        return cls(
            eligible_outcome_count=risk.eligible_outcome_count,
            average_mae_10d=risk.average_mae_10d,
            worst_mae_10d=risk.worst_mae_10d,
            average_mfe_10d=risk.average_mfe_10d,
            best_mfe_10d=risk.best_mfe_10d,
        )


class RegimeEvidenceSchema(BaseModel):
    close: Optional[float]
    sma20: Optional[float]
    sma50: Optional[float]
    close_vs_sma20: Optional[str]
    sma20_vs_sma50: Optional[str]

    @classmethod
    def from_domain(cls, evidence: RegimeEvidence) -> "RegimeEvidenceSchema":
        return cls(
            close=evidence.close,
            sma20=evidence.sma20,
            sma50=evidence.sma50,
            close_vs_sma20=evidence.close_vs_sma20.value if evidence.close_vs_sma20 else None,
            sma20_vs_sma50=evidence.sma20_vs_sma50.value if evidence.sma20_vs_sma50 else None,
        )


class RiskMarketContextSchema(BaseModel):
    annualized_realized_volatility_20: Optional[float]
    regime: str
    regime_evidence: RegimeEvidenceSchema

    @classmethod
    def from_domain(cls, context: RiskMarketContext) -> "RiskMarketContextSchema":
        return cls(
            annualized_realized_volatility_20=context.annualized_realized_volatility_20,
            regime=context.regime.value,
            regime_evidence=RegimeEvidenceSchema.from_domain(context.regime_evidence),
        )


class StrategyAuditResponse(BaseModel):
    provider_symbol: str
    interval: str
    strategy_id: str
    strategy_name: str
    audit_date: Date
    evaluation: StrategyEvaluationSchema
    historical_evidence: HistoricalSignalEvidenceSchema
    historical_signal_risk: HistoricalSignalRiskSchema
    risk_market_context: RiskMarketContextSchema
    retrospective_outcome: Optional[SignalOutcomeSchema]

    @classmethod
    def from_domain(cls, audit: StrategyAudit) -> "StrategyAuditResponse":
        return cls(
            provider_symbol=audit.provider_symbol,
            interval=audit.interval,
            strategy_id=audit.strategy_id,
            strategy_name=audit.strategy_name,
            audit_date=audit.audit_date,
            evaluation=StrategyEvaluationSchema.from_domain(audit.evaluation),
            historical_evidence=HistoricalSignalEvidenceSchema.from_domain(audit.historical_evidence),
            historical_signal_risk=HistoricalSignalRiskSchema.from_domain(audit.historical_signal_risk),
            risk_market_context=RiskMarketContextSchema.from_domain(audit.risk_market_context),
            retrospective_outcome=SignalOutcomeSchema.from_domain(audit.retrospective_outcome)
            if audit.retrospective_outcome
            else None,
        )
