import pytest

from app.indicators.rsi import rsi_wilder


# ---------------------------------------------------------------------------
# Independently hand-derived reference fixture (period=3, for tractable manual
# arithmetic — same algorithm/code path as period=14, only the window differs).
#
# closes = [100, 102, 101, 105, 103, 107, 106]
# deltas:  d1=+2 d2=-1 d3=+4 d4=-2 d5=+4 d6=-1
# gains:   [2,0,4,0,4,0]   losses: [0,1,0,2,0,1]
#
# Seed (bar index 3, using deltas d1..d3):
#   avg_gain = (2+0+4)/3 = 2           avg_loss = (0+1+0)/3 = 1/3
#   RS = 6                              RSI = 100 - 100/7 = 85.714285714285714...
#
# Bar index 4 (Wilder smoothing with d4: gain=0, loss=2):
#   avg_gain = (2*2+0)/3 = 4/3          avg_loss = ((1/3)*2+2)/3 = 8/9
#   RS = (4/3)/(8/9) = 1.5              RSI = 100 - 100/2.5 = 60.0
#
# Bar index 5 (d5: gain=4, loss=0):
#   avg_gain = ((4/3)*2+4)/3 = 20/9     avg_loss = ((8/9)*2+0)/3 = 16/27
#   RS = 3.75                           RSI = 100 - 100/4.75 = 78.94736842105263
#
# Bar index 6 (d6: gain=0, loss=1):
#   avg_gain = ((20/9)*2+0)/3 = 40/27   avg_loss = ((16/27)*2+1)/3 = 59/81
#   RS = (40/27)/(59/81) = 120/59       RSI = 100 - 100/(179/59) = 67.03910614525139
# ---------------------------------------------------------------------------

REFERENCE_CLOSES = [100, 102, 101, 105, 103, 107, 106]
REFERENCE_RSI = {
    3: 85.714285714285714,
    4: 60.0,
    5: 78.94736842105263,
    6: 67.03910614525139,
}


def test_hand_derived_reference_fixture():
    result = rsi_wilder(REFERENCE_CLOSES, period=3)
    assert result[0] is None
    assert result[1] is None
    assert result[2] is None
    for index, expected in REFERENCE_RSI.items():
        assert result[index] == pytest.approx(expected, abs=1e-9)


def test_warm_up_boundary_period_14():
    # 15 varying closes (14 deltas): first 14 bars (indices 0..13) unavailable,
    # the 15th (index 14) is the first with a full 14-period window.
    closes = [100, 101, 99, 102, 103, 101, 104, 105, 103, 106, 107, 105, 108, 109, 107]
    assert len(closes) == 15
    result = rsi_wilder(closes, period=14)
    assert all(v is None for v in result[:14])
    assert result[14] is not None


def test_insufficient_history_returns_all_none():
    closes = [100, 101, 102]  # fewer than period+1 = 15
    result = rsi_wilder(closes, period=14)
    assert result == [None] * 3


def test_all_gains_produces_rsi_100():
    closes = list(range(100, 116))  # strictly increasing, 15 values -> 14 gains
    result = rsi_wilder(closes, period=14)
    assert result[14] == pytest.approx(100.0)


def test_all_losses_produces_rsi_0():
    closes = list(range(116, 100, -1))  # strictly decreasing, 15 values -> 14 losses
    result = rsi_wilder(closes, period=14)
    assert result[14] == pytest.approx(0.0)


def test_flat_market_produces_rsi_50():
    closes = [100.0] * 20
    result = rsi_wilder(closes, period=14)
    assert result[14] == pytest.approx(50.0)
    assert result[19] == pytest.approx(50.0)


def test_no_look_ahead():
    prefix = REFERENCE_CLOSES
    result_before = rsi_wilder(prefix, period=3)

    extended = prefix + [10000, -5000, 8000]
    result_after = rsi_wilder(extended, period=3)

    assert result_after[: len(prefix)] == result_before
