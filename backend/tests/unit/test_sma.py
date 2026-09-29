import pytest

from app.indicators.sma import sma


def test_exact_sma_calculation():
    # window=3: SMA[2]=mean(1,2,3)=2, SMA[3]=mean(2,3,4)=3, SMA[4]=mean(3,4,5)=4
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = sma(values, window=3)
    assert result[0] is None
    assert result[1] is None
    assert result[2] == pytest.approx(2.0)
    assert result[3] == pytest.approx(3.0)
    assert result[4] == pytest.approx(4.0)


def test_sma20_warm_up_boundary():
    values = [10.0] * 30
    result = sma(values, window=20)
    assert all(v is None for v in result[:19])
    assert result[19] == pytest.approx(10.0)
    assert result[20] == pytest.approx(10.0)


def test_sma50_warm_up_boundary():
    values = list(range(1, 61))  # 60 values: 1..60
    result = sma(values, window=50)
    assert all(v is None for v in result[:49])
    # SMA at index49 = mean(1..50) = 25.5
    assert result[49] == pytest.approx(25.5)
    # SMA at index50 = mean(2..51) = 26.5
    assert result[50] == pytest.approx(26.5)


def test_insufficient_data_returns_all_none():
    values = [1.0, 2.0, 3.0]
    result = sma(values, window=20)
    assert result == [None, None, None]


def test_constant_price_input():
    values = [42.0] * 25
    result = sma(values, window=20)
    valid = [v for v in result if v is not None]
    assert all(v == pytest.approx(42.0) for v in valid)
    assert len(valid) == 6  # indices 19..24


def test_no_look_ahead():
    prefix = [1.0, 2.0, 3.0, 4.0, 5.0]
    result_before = sma(prefix, window=3)

    extended = prefix + [1000.0, -500.0, 999.0]  # dramatically different future
    result_after = sma(extended, window=3)

    assert result_after[: len(prefix)] == result_before
