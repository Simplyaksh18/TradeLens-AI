import copy
from datetime import date, timedelta

import pytest

from app.market_data.models import OHLCVBar, OHLCVSeries
from app.market_data.validation.models import IssueCode, IssueSeverity
from app.market_data.validation.validator import validate_ohlcv_series


def _bar(d, o=100.0, h=105.0, l=99.0, c=102.0, adj=102.0, v=1000):
    return OHLCVBar(date=d, open=o, high=h, low=l, close=c, adj_close=adj, volume=v)


def _series(bars, symbol="RELIANCE.NS", interval="1d"):
    return OHLCVSeries(provider_symbol=symbol, interval=interval, bars=tuple(bars))


D1, D2, D3 = date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)


# ---------------------------------------------------------------------------
# Valid cases
# ---------------------------------------------------------------------------


def test_ordinary_valid_dataset_has_no_issues():
    series = _series([_bar(D1), _bar(D2), _bar(D3)])
    report = validate_ohlcv_series(series)
    assert report.is_valid
    assert report.error_count == 0
    assert report.warning_count == 0
    # Phase 1B deliberately never emits INFO-severity issues (see CLAUDE.md
    # guidance against manufacturing them); the property must still compute.
    assert report.info_count == 0
    assert report.rows_inspected == 3


def test_close_differing_from_adj_close_is_not_an_issue():
    series = _series([_bar(D1, c=102.0, adj=95.0)])
    report = validate_ohlcv_series(series)
    assert report.is_valid
    assert not any(i.code == IssueCode.ADJ_CLOSE_NON_POSITIVE for i in report.issues)


def test_zero_volume_is_warning_not_error():
    series = _series([_bar(D1, v=0)])
    report = validate_ohlcv_series(series)
    assert report.is_valid  # WARNING does not affect validity
    codes = [i.code for i in report.issues]
    assert IssueCode.VOLUME_ZERO in codes
    zero_issue = next(i for i in report.issues if i.code == IssueCode.VOLUME_ZERO)
    assert zero_issue.severity is IssueSeverity.WARNING


def test_negative_volume_is_error():
    series = _series([_bar(D1, v=-5)])
    report = validate_ohlcv_series(series)
    assert not report.is_valid
    issue = next(i for i in report.issues if i.code == IssueCode.VOLUME_NEGATIVE)
    assert issue.severity is IssueSeverity.ERROR


# ---------------------------------------------------------------------------
# Dataset-level
# ---------------------------------------------------------------------------


def test_empty_dataset_is_error():
    report = validate_ohlcv_series(_series([]))
    assert not report.is_valid
    assert report.rows_inspected == 0
    assert [i.code for i in report.issues] == [IssueCode.EMPTY_DATASET]
    assert report.issues[0].severity is IssueSeverity.ERROR


def test_duplicate_trading_date_is_error():
    series = _series([_bar(D1), _bar(D1, c=200.0), _bar(D2)])
    report = validate_ohlcv_series(series)
    assert not report.is_valid
    issue = next(i for i in report.issues if i.code == IssueCode.DUPLICATE_TRADING_DATE)
    assert issue.date == D1
    assert issue.observed_value == 2


def test_non_monotonic_dates_is_error():
    series = _series([_bar(D2), _bar(D1), _bar(D3)])
    report = validate_ohlcv_series(series)
    assert not report.is_valid
    assert any(i.code == IssueCode.NON_MONOTONIC_DATES for i in report.issues)


# ---------------------------------------------------------------------------
# OHLC field validity: null/NaN/+inf/-inf/zero/negative, parameterized
# ---------------------------------------------------------------------------

_FIELDS = ["open", "high", "low", "close"]
_FIELD_TO_KWARG = {"open": "o", "high": "h", "low": "l", "close": "c"}
_INVALID_NOT_FINITE = [float("nan"), float("inf"), float("-inf")]
_INVALID_NON_POSITIVE = [0.0, -10.0]


@pytest.mark.parametrize("field", _FIELDS)
@pytest.mark.parametrize("bad_value", _INVALID_NOT_FINITE)
def test_ohlc_field_not_finite_is_error(field, bad_value):
    kwargs = {_FIELD_TO_KWARG[field]: bad_value}
    series = _series([_bar(D1, **kwargs)])
    report = validate_ohlcv_series(series)
    assert not report.is_valid
    issue = next(i for i in report.issues if i.code == IssueCode.FIELD_NOT_FINITE)
    assert issue.field == field
    assert issue.date == D1


@pytest.mark.parametrize("field", _FIELDS)
@pytest.mark.parametrize("bad_value", _INVALID_NON_POSITIVE)
def test_ohlc_field_non_positive_is_error(field, bad_value):
    # Base values are internally consistent; only the target field is
    # overridden. Other relationship issues may also fire on the same bar
    # (acceptable — a malformed bar can legitimately trigger multiple
    # issues) but FIELD_NON_POSITIVE for this exact field must be present.
    kwargs = {_FIELD_TO_KWARG[field]: bad_value}
    series = _series([_bar(D1, **kwargs)])
    report = validate_ohlcv_series(series)
    assert not report.is_valid
    issue = next(i for i in report.issues if i.code == IssueCode.FIELD_NON_POSITIVE and i.field == field)
    assert issue.date == D1


# ---------------------------------------------------------------------------
# OHLC relationship violations
# ---------------------------------------------------------------------------


def test_high_below_low_is_error():
    series = _series([_bar(D1, h=90.0, l=99.0, o=95.0, c=95.0)])
    report = validate_ohlcv_series(series)
    assert IssueCode.OHLC_HIGH_LOW_INVERTED in [i.code for i in report.issues]


def test_high_below_open_is_error():
    series = _series([_bar(D1, h=90.0, o=95.0, l=80.0, c=85.0)])
    report = validate_ohlcv_series(series)
    assert IssueCode.OHLC_HIGH_BELOW_OPEN in [i.code for i in report.issues]


def test_high_below_close_is_error():
    series = _series([_bar(D1, h=90.0, c=95.0, o=85.0, l=80.0)])
    report = validate_ohlcv_series(series)
    assert IssueCode.OHLC_HIGH_BELOW_CLOSE in [i.code for i in report.issues]


def test_low_above_open_is_error():
    series = _series([_bar(D1, l=95.0, o=90.0, h=100.0, c=96.0)])
    report = validate_ohlcv_series(series)
    assert IssueCode.OHLC_LOW_ABOVE_OPEN in [i.code for i in report.issues]


def test_low_above_close_is_error():
    series = _series([_bar(D1, l=95.0, c=90.0, o=96.0, h=100.0)])
    report = validate_ohlcv_series(series)
    assert IssueCode.OHLC_LOW_ABOVE_CLOSE in [i.code for i in report.issues]


def test_single_bar_can_trigger_multiple_relationship_violations():
    # high below everything, low above everything: a structurally impossible bar
    series = _series([_bar(D1, o=50.0, h=10.0, l=60.0, c=55.0)])
    report = validate_ohlcv_series(series)
    codes = {i.code for i in report.issues}
    assert IssueCode.OHLC_HIGH_LOW_INVERTED in codes
    assert IssueCode.OHLC_HIGH_BELOW_OPEN in codes
    assert IssueCode.OHLC_HIGH_BELOW_CLOSE in codes
    assert IssueCode.OHLC_LOW_ABOVE_OPEN in codes
    assert IssueCode.OHLC_LOW_ABOVE_CLOSE in codes


# ---------------------------------------------------------------------------
# adj_close
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_value", [None, float("nan")])
def test_adj_close_missing_is_error(bad_value):
    series = _series([_bar(D1, adj=bad_value)])
    report = validate_ohlcv_series(series)
    assert not report.is_valid
    assert any(i.code == IssueCode.ADJ_CLOSE_MISSING for i in report.issues)


@pytest.mark.parametrize("bad_value", [float("inf"), float("-inf")])
def test_adj_close_infinite_is_error(bad_value):
    series = _series([_bar(D1, adj=bad_value)])
    report = validate_ohlcv_series(series)
    assert not report.is_valid
    assert any(i.code == IssueCode.ADJ_CLOSE_NOT_FINITE for i in report.issues)


@pytest.mark.parametrize("bad_value", [0.0, -1.0])
def test_adj_close_non_positive_is_error(bad_value):
    series = _series([_bar(D1, adj=bad_value)])
    report = validate_ohlcv_series(series)
    assert not report.is_valid
    assert any(i.code == IssueCode.ADJ_CLOSE_NON_POSITIVE for i in report.issues)


def test_adj_close_valid_and_different_from_close_is_fine():
    series = _series([_bar(D1, c=100.0, adj=88.5)])
    report = validate_ohlcv_series(series)
    assert report.is_valid


# ---------------------------------------------------------------------------
# volume
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_value", [None, float("nan")])
def test_volume_missing_is_error(bad_value):
    series = _series([_bar(D1, v=bad_value)])
    report = validate_ohlcv_series(series)
    assert not report.is_valid
    assert any(i.code == IssueCode.VOLUME_MISSING for i in report.issues)


@pytest.mark.parametrize("bad_value", [float("inf"), float("-inf")])
def test_volume_infinite_is_error(bad_value):
    series = _series([_bar(D1, v=bad_value)])
    report = validate_ohlcv_series(series)
    assert not report.is_valid
    assert any(i.code == IssueCode.VOLUME_NOT_FINITE for i in report.issues)


def test_volume_positive_is_valid():
    series = _series([_bar(D1, v=12345)])
    report = validate_ohlcv_series(series)
    assert report.is_valid


# ---------------------------------------------------------------------------
# Calendar gaps must NOT be treated as missing-bar errors
# ---------------------------------------------------------------------------


def test_weekend_style_multi_day_gap_is_not_reported_as_missing_bar():
    friday = date(2024, 1, 5)
    monday = date(2024, 1, 8)  # 3 calendar days later, legitimate weekend gap
    series = _series([_bar(friday), _bar(monday)])
    report = validate_ohlcv_series(series)
    assert report.is_valid
    assert not any("MISSING" in i.code.value for i in report.issues)


# ---------------------------------------------------------------------------
# Reporting contract
# ---------------------------------------------------------------------------


def test_report_counts_and_status_are_consistent():
    series = _series([_bar(D1, v=0), _bar(D2, v=-1)])
    report = validate_ohlcv_series(series)
    assert report.warning_count == 1
    assert report.error_count == 1
    assert report.is_valid is False
    assert report.provider_symbol == "RELIANCE.NS"
    assert report.interval == "1d"


def test_validation_is_deterministic_across_repeated_runs():
    series = _series([_bar(D1, v=0), _bar(D3), _bar(D2, h=1.0, l=99.0, o=1.0, c=1.0)])
    report1 = validate_ohlcv_series(series)
    report2 = validate_ohlcv_series(series)
    assert report1.issues == report2.issues


# ---------------------------------------------------------------------------
# Non-mutation
# ---------------------------------------------------------------------------


def test_validation_does_not_mutate_input_series():
    original = _series([_bar(D2), _bar(D1), _bar(D3, v=0)])
    snapshot = copy.deepcopy(original)

    validate_ohlcv_series(original)

    assert original == snapshot
    assert original.bars is snapshot.bars or original.bars == snapshot.bars
    assert [b.date for b in original.bars] == [b.date for b in snapshot.bars]
