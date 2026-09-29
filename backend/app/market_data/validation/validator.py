"""Deterministic OHLCV data-quality validator.

Operates ONLY on TradeLens's already-normalized `OHLCVSeries`/`OHLCVBar`
(see app.market_data.models) — never on provider-specific structures. It is
observational: it detects and reports issues, and never mutates, sorts,
deduplicates, or repairs the input.

Scope boundary (see CLAUDE.md Phase 1B): this module assumes Phase 1A already
converted whatever the provider returned into these dataclasses. It does not
parse dates/strings and does not know about yfinance.

Normalized-contract notes this validator relies on (see Phase 1B
pre-implementation note for the full discovery):
  - `OHLCVBar.date` is always a real `datetime.date` — the field is
    non-Optional, and yfinance normalization explicitly rejects a missing/NaT
    provider timestamp with `MalformedProviderResponseError` before a bar is
    ever constructed (fixed post-Phase-1B; see CLAUDE.md). NaT/null dates are
    therefore not representable here, so no such check is implemented in
    this validator.
  - `OHLCVBar.open/high/low/close` are always Python `float`, but CAN
    genuinely be NaN or +/-inf: `normalize_yfinance_history` casts with a
    bare `float(...)`, so a NaN/inf value already present at the provider
    survives normalization unchanged. This validator is what actually catches
    that.
  - `OHLCVBar.adj_close` is `Optional[float]`: normalization maps a NaN
    provider value to `None`, but an inf provider value survives as `inf`.
  - `OHLCVBar.volume` is typed `int`; the *current* normalization path
    cannot produce NaN or +/-inf volume — both are now explicitly rejected
    with `MalformedProviderResponseError` (fixed post-Phase-1B; see
    CLAUDE.md). Negative and zero volume ARE reachable (no sign check
    upstream). This validator still checks volume for None/NaN/inf
    defensively: `OHLCVSeries` is a plain dataclass with no runtime type
    enforcement, so any future provider or directly-constructed series could
    still place such a value in this field.
  - Duplicate dates and non-ascending order are NOT prevented by the
    `OHLCVSeries`/`OHLCVBar` dataclasses themselves (only by the specific
    code path that happens to build them today), so both are validated here.
  - "Required field structurally absent" is not representable: every
    `OHLCVBar` field is a required constructor argument with no default, so
    a bar missing e.g. `close` cannot exist as a Python object in the first
    place. Only the dataset-level "zero bars" case is checked instead.

Calendar completeness (weekends/exchange holidays) is explicitly NOT
validated — see CLAUDE.md Phase 1B scope: NSE trading-calendar awareness is
a deliberately deferred capability, not a Phase 1B gap.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.market_data.models import OHLCVSeries
from app.market_data.validation.models import (
    DataQualityIssue,
    DataQualityReport,
    IssueCode,
    IssueSeverity,
)

_OHLC_FIELDS = ("open", "high", "low", "close")


def validate_ohlcv_series(series: OHLCVSeries) -> DataQualityReport:
    """Inspect a normalized OHLCV series and report data-quality issues.

    Read-only: never mutates `series` or anything reachable from it.
    """
    bars = series.bars
    rows_inspected = len(bars)

    if rows_inspected == 0:
        issue = DataQualityIssue(
            code=IssueCode.EMPTY_DATASET,
            severity=IssueSeverity.ERROR,
            message="Normalized dataset contains zero bars.",
        )
        return DataQualityReport(series.provider_symbol, series.interval, 0, (issue,))

    df = pd.DataFrame(
        {
            "date": [b.date for b in bars],
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "adj_close": [b.adj_close for b in bars],
            "volume": [b.volume for b in bars],
        }
    )

    issues: list[DataQualityIssue] = []
    issues.extend(_check_duplicate_dates(df))
    issues.extend(_check_ordering(df))
    for field in _OHLC_FIELDS:
        issues.extend(_check_numeric_field(df, field, IssueCode.FIELD_NOT_FINITE, IssueCode.FIELD_NON_POSITIVE))
    issues.extend(_check_ohlc_relationships(df))
    issues.extend(_check_adj_close(df))
    issues.extend(_check_volume(df))

    return DataQualityReport(series.provider_symbol, series.interval, rows_inspected, tuple(issues))


def _check_duplicate_dates(df: pd.DataFrame) -> list[DataQualityIssue]:
    counts = df["date"].value_counts()
    duplicated_dates = sorted(d for d, count in counts.items() if count > 1)
    return [
        DataQualityIssue(
            code=IssueCode.DUPLICATE_TRADING_DATE,
            severity=IssueSeverity.ERROR,
            message=f"Trading date {d} appears {int(counts[d])} times.",
            date=d,
            field="date",
            observed_value=int(counts[d]),
        )
        for d in duplicated_dates
    ]


def _check_ordering(df: pd.DataFrame) -> list[DataQualityIssue]:
    dates = df["date"].tolist()
    if dates != sorted(dates):
        return [
            DataQualityIssue(
                code=IssueCode.NON_MONOTONIC_DATES,
                severity=IssueSeverity.ERROR,
                message="Trading dates are not in strictly ascending order.",
                field="date",
            )
        ]
    return []


def _check_numeric_field(
    df: pd.DataFrame,
    field: str,
    not_finite_code: IssueCode,
    non_positive_code: IssueCode,
) -> list[DataQualityIssue]:
    """Shared logic for a required numeric field (OHLC prices).

    Deliberately checks finiteness BEFORE positivity, and does not rely on
    `<= 0` alone to catch invalid values: NaN fails an ordinary `<= 0`
    comparison (NaN <= 0 is False), so a naive positivity-only check would
    silently miss NaN prices.
    """
    values = df[field].astype(float)
    finite_mask = np.isfinite(values)

    issues = [
        DataQualityIssue(
            code=not_finite_code,
            severity=IssueSeverity.ERROR,
            message=f"{field} is not a finite number.",
            date=row.date,
            field=field,
            observed_value=getattr(row, field),
        )
        for row in df.loc[~finite_mask].itertuples()
    ]

    non_positive_mask = finite_mask & (values <= 0)
    issues.extend(
        DataQualityIssue(
            code=non_positive_code,
            severity=IssueSeverity.ERROR,
            message=f"{field} must be > 0.",
            date=row.date,
            field=field,
            observed_value=getattr(row, field),
        )
        for row in df.loc[non_positive_mask].itertuples()
    )
    return issues


def _check_ohlc_relationships(df: pd.DataFrame) -> list[DataQualityIssue]:
    """NaN-safe by construction: any comparison involving NaN evaluates to
    False in pandas/NumPy, so a bar already flagged as non-finite does not
    also spuriously trigger a relationship violation here."""
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]

    checks = [
        (h < l, IssueCode.OHLC_HIGH_LOW_INVERTED, "high < low"),
        (h < o, IssueCode.OHLC_HIGH_BELOW_OPEN, "high < open"),
        (h < c, IssueCode.OHLC_HIGH_BELOW_CLOSE, "high < close"),
        (l > o, IssueCode.OHLC_LOW_ABOVE_OPEN, "low > open"),
        (l > c, IssueCode.OHLC_LOW_ABOVE_CLOSE, "low > close"),
    ]

    issues: list[DataQualityIssue] = []
    for mask, code, description in checks:
        for row in df.loc[mask].itertuples():
            issues.append(
                DataQualityIssue(
                    code=code,
                    severity=IssueSeverity.ERROR,
                    message=f"Invalid OHLC relationship: {description} (open={row.open}, "
                    f"high={row.high}, low={row.low}, close={row.close}).",
                    date=row.date,
                    field="open,high,low,close",
                )
            )
    return issues


def _check_adj_close(df: pd.DataFrame) -> list[DataQualityIssue]:
    values = df["adj_close"]
    is_missing = values.isna()  # catches both None and NaN

    issues = [
        DataQualityIssue(
            code=IssueCode.ADJ_CLOSE_MISSING,
            severity=IssueSeverity.ERROR,
            message="adj_close is missing (null/NaN).",
            date=row.date,
            field="adj_close",
        )
        for row in df.loc[is_missing].itertuples()
    ]

    present = values[~is_missing].astype(float)
    not_finite_mask = ~np.isfinite(present)
    for idx in present[not_finite_mask].index:
        row = df.loc[idx]
        issues.append(
            DataQualityIssue(
                code=IssueCode.ADJ_CLOSE_NOT_FINITE,
                severity=IssueSeverity.ERROR,
                message="adj_close is infinite.",
                date=row["date"],
                field="adj_close",
                observed_value=row["adj_close"],
            )
        )

    non_positive_mask = np.isfinite(present) & (present <= 0)
    for idx in present[non_positive_mask].index:
        row = df.loc[idx]
        issues.append(
            DataQualityIssue(
                code=IssueCode.ADJ_CLOSE_NON_POSITIVE,
                severity=IssueSeverity.ERROR,
                message="adj_close must be > 0.",
                date=row["date"],
                field="adj_close",
                observed_value=row["adj_close"],
            )
        )
    return issues


def _check_volume(df: pd.DataFrame) -> list[DataQualityIssue]:
    """Fixed zero-volume policy (approved, not implementation discretion):
    volume < 0 -> ERROR, volume == 0 -> WARNING, volume > 0 -> valid.
    """
    values = df["volume"]
    is_missing = values.isna()

    issues = [
        DataQualityIssue(
            code=IssueCode.VOLUME_MISSING,
            severity=IssueSeverity.ERROR,
            message="volume is missing (null/NaN).",
            date=row.date,
            field="volume",
        )
        for row in df.loc[is_missing].itertuples()
    ]

    present = values[~is_missing]
    present_float = present.astype(float)
    not_finite_mask = ~np.isfinite(present_float)
    for idx in present[not_finite_mask].index:
        row = df.loc[idx]
        issues.append(
            DataQualityIssue(
                code=IssueCode.VOLUME_NOT_FINITE,
                severity=IssueSeverity.ERROR,
                message="volume is infinite.",
                date=row["date"],
                field="volume",
                observed_value=row["volume"],
            )
        )

    finite_present = present[np.isfinite(present_float)]
    negative_mask = finite_present < 0
    for idx in finite_present[negative_mask].index:
        row = df.loc[idx]
        issues.append(
            DataQualityIssue(
                code=IssueCode.VOLUME_NEGATIVE,
                severity=IssueSeverity.ERROR,
                message="volume must not be negative.",
                date=row["date"],
                field="volume",
                observed_value=row["volume"],
            )
        )

    zero_mask = finite_present == 0
    for idx in finite_present[zero_mask].index:
        row = df.loc[idx]
        issues.append(
            DataQualityIssue(
                code=IssueCode.VOLUME_ZERO,
                severity=IssueSeverity.WARNING,
                message="volume is zero.",
                date=row["date"],
                field="volume",
                observed_value=row["volume"],
            )
        )

    return issues
