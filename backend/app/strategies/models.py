"""Frozen typed evidence contract for Phase 1D strategy evaluation.

No P&L/return/outcome/confidence/score/prediction/probability/position/
recommendation field belongs here — this phase only explains what the
strategy decided and why, never whether it was profitable or what to do
next (that is later phases' responsibility).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from enum import Enum


class StrategyDecision(str, Enum):
    BUY = "BUY"
    NO_SIGNAL = "NO_SIGNAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class NamedValue:
    name: str
    value: float


@dataclass(frozen=True)
class ConditionResult:
    condition_id: str
    description: str
    passed: bool
    actual_values: tuple[NamedValue, ...]
    operator: str
    reference_values: tuple[NamedValue, ...] = ()


@dataclass(frozen=True)
class StrategyEvaluation:
    date: Date
    strategy_id: str
    strategy_name: str
    decision: StrategyDecision
    conditions: tuple[ConditionResult, ...]
    missing_inputs: tuple[str, ...]


@dataclass(frozen=True)
class StrategyEvaluationSeries:
    provider_symbol: str
    interval: str
    strategy_id: str
    strategy_name: str
    evaluations: tuple[StrategyEvaluation, ...]
