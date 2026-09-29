from __future__ import annotations

from datetime import date as Date

from pydantic import BaseModel

from app.api.schemas.common import NamedValueSchema
from app.strategies.models import ConditionResult, StrategyEvaluation, StrategyEvaluationSeries


class ConditionResultSchema(BaseModel):
    condition_id: str
    description: str
    passed: bool
    actual_values: list[NamedValueSchema]
    operator: str
    reference_values: list[NamedValueSchema]

    @classmethod
    def from_domain(cls, condition: ConditionResult) -> "ConditionResultSchema":
        return cls(
            condition_id=condition.condition_id,
            description=condition.description,
            passed=condition.passed,
            actual_values=[NamedValueSchema.from_domain(v) for v in condition.actual_values],
            operator=condition.operator,
            reference_values=[NamedValueSchema.from_domain(v) for v in condition.reference_values],
        )


class StrategyEvaluationSchema(BaseModel):
    date: Date
    strategy_id: str
    strategy_name: str
    decision: str
    conditions: list[ConditionResultSchema]
    missing_inputs: list[str]

    @classmethod
    def from_domain(cls, evaluation: StrategyEvaluation) -> "StrategyEvaluationSchema":
        return cls(
            date=evaluation.date,
            strategy_id=evaluation.strategy_id,
            strategy_name=evaluation.strategy_name,
            decision=evaluation.decision.value,
            conditions=[ConditionResultSchema.from_domain(c) for c in evaluation.conditions],
            missing_inputs=list(evaluation.missing_inputs),
        )


class StrategyEvaluationSeriesResponse(BaseModel):
    provider_symbol: str
    interval: str
    strategy_id: str
    strategy_name: str
    evaluations: list[StrategyEvaluationSchema]

    @classmethod
    def from_domain(cls, series: StrategyEvaluationSeries) -> "StrategyEvaluationSeriesResponse":
        return cls(
            provider_symbol=series.provider_symbol,
            interval=series.interval,
            strategy_id=series.strategy_id,
            strategy_name=series.strategy_name,
            evaluations=[StrategyEvaluationSchema.from_domain(e) for e in series.evaluations],
        )
