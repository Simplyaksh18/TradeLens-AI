import pytest

from app.indicators.volume import rolling_average_volume, volume_ratio


# ---------------------------------------------------------------------------
# Approved definition (given, not chosen here): rolling average volume at T
# is the mean of the PREVIOUS `window` completed bars, excluding bar T.
# volume_ratio at T = Volume[T] / that previous-window average.
# ---------------------------------------------------------------------------


def test_exact_rolling_average_volume_small_window():
    # window=3: avg[3] = mean(volumes[0:3]) = mean(10,20,30) = 20
    #           avg[4] = mean(volumes[1:4]) = mean(20,30,5)  = 18.333...
    volumes = [10, 20, 30, 5, 40]
    result = rolling_average_volume(volumes, window=3)
    assert result[0] is None
    assert result[1] is None
    assert result[2] is None
    assert result[3] == pytest.approx(20.0)
    assert result[4] == pytest.approx(18.333333333333332)


def test_exact_volume_ratio_small_window():
    volumes = [10, 20, 30, 5, 40]
    result = volume_ratio(volumes, window=3)
    # ratio[3] = volumes[3] / avg[3] = 5 / 20 = 0.25
    assert result[3] == pytest.approx(0.25)
    # ratio[4] = 40 / mean(20,30,5) = 40 / (55/3) = 2.1818...
    assert result[4] == pytest.approx(40 / (55 / 3))


def test_rolling_average_volume_warm_up_default_window():
    volumes = list(range(1, 26))  # 25 values: 1..25
    result = rolling_average_volume(volumes)  # default window=20

    assert all(v is None for v in result[:20])
    # avg[20] = mean(volumes[0:20]) = mean(1..20) = 10.5
    assert result[20] == pytest.approx(10.5)


def test_volume_ratio_default_window_round_number_case():
    volumes = list(range(1, 26))
    result = volume_ratio(volumes)
    # ratio[20] = volumes[20]/avg[20] = 21/10.5 = 2.0
    assert result[20] == pytest.approx(2.0)


def test_zero_denominator_produces_none_not_inf_or_nan():
    volumes = [0] * 20 + [50]
    averages = rolling_average_volume(volumes)
    ratios = volume_ratio(volumes)

    assert averages[20] == pytest.approx(0.0)  # the average itself is a legitimate 0
    assert ratios[20] is None  # but the ratio is explicitly unavailable, not inf/NaN


def test_insufficient_history_returns_all_none():
    volumes = [10, 20, 30]
    assert rolling_average_volume(volumes, window=20) == [None, None, None]
    assert volume_ratio(volumes, window=20) == [None, None, None]


def test_no_look_ahead_average_volume():
    prefix = [10, 20, 30, 5, 40]
    result_before = rolling_average_volume(prefix, window=3)

    extended = prefix + [999999, 1, 500000]
    result_after = rolling_average_volume(extended, window=3)

    assert result_after[: len(prefix)] == result_before


def test_no_look_ahead_volume_ratio():
    prefix = [10, 20, 30, 5, 40]
    result_before = volume_ratio(prefix, window=3)

    extended = prefix + [999999, 1, 500000]
    result_after = volume_ratio(extended, window=3)

    assert result_after[: len(prefix)] == result_before
