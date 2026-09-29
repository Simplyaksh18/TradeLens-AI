"""Structured output contract for OHLCV data-quality validation.

Kept deliberately small: one issue model, one report model, two enums.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from enum import Enum
from typing import Optional


class IssueSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class IssueCode(str, Enum):
    EMPTY_DATASET = "EMPTY_DATASET"
    DUPLICATE_TRADING_DATE = "DUPLICATE_TRADING_DATE"
    NON_MONOTONIC_DATES = "NON_MONOTONIC_DATES"

    FIELD_NOT_FINITE = "FIELD_NOT_FINITE"
    FIELD_NON_POSITIVE = "FIELD_NON_POSITIVE"

    OHLC_HIGH_LOW_INVERTED = "OHLC_HIGH_LOW_INVERTED"
    OHLC_HIGH_BELOW_OPEN = "OHLC_HIGH_BELOW_OPEN"
    OHLC_HIGH_BELOW_CLOSE = "OHLC_HIGH_BELOW_CLOSE"
    OHLC_LOW_ABOVE_OPEN = "OHLC_LOW_ABOVE_OPEN"
    OHLC_LOW_ABOVE_CLOSE = "OHLC_LOW_ABOVE_CLOSE"

    ADJ_CLOSE_MISSING = "ADJ_CLOSE_MISSING"
    ADJ_CLOSE_NOT_FINITE = "ADJ_CLOSE_NOT_FINITE"
    ADJ_CLOSE_NON_POSITIVE = "ADJ_CLOSE_NON_POSITIVE"

    VOLUME_MISSING = "VOLUME_MISSING"
    VOLUME_NOT_FINITE = "VOLUME_NOT_FINITE"
    VOLUME_NEGATIVE = "VOLUME_NEGATIVE"
    VOLUME_ZERO = "VOLUME_ZERO"


@dataclass(frozen=True)
class DataQualityIssue:
    code: IssueCode
    severity: IssueSeverity
    message: str
    date: Optional[Date] = None
    field: Optional[str] = None
    observed_value: Optional[object] = None


@dataclass(frozen=True)
class DataQualityReport:
    provider_symbol: str
    interval: str
    rows_inspected: int
    issues: tuple[DataQualityIssue, ...]

    @property
    def is_valid(self) -> bool:
        """True iff no ERROR-severity issue was found. WARNING/INFO issues
        do not affect validity — the dataset remains usable for downstream
        quantitative calculations, just worth surfacing."""
        return not any(i.severity is IssueSeverity.ERROR for i in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity is IssueSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity is IssueSeverity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity is IssueSeverity.INFO)
