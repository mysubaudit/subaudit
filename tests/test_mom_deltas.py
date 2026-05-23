"""
test_mom_deltas.py — Tests for calculate_mom_deltas() (v3.3 Step 8)
"""
import pytest
from app.core.snapshot import calculate_mom_deltas


# ---------------------------------------------------------------------------
# Test 1: two snapshots — correct deltas
# ---------------------------------------------------------------------------
def test_mom_deltas_basic():
    """Two snapshots: one month apart. Positive MRR growth, churn down, NRR up."""
    history = {
        "periods": ["2024-01", "2024-02"],
        "mrr": [1000.0, 1100.0],
        "churn_rate": [3.5, 3.0],
        "nrr": [95.0, 98.0],
    }
    result = calculate_mom_deltas(history)

    assert result is not None
    assert result["period"]["current"] == "2024-02"
    assert result["period"]["previous"] == "2024-01"

    # MRR: +10%
    assert result["mrr"]["current"] == 1100.0
    assert result["mrr"]["previous"] == 1000.0
    assert result["mrr"]["delta_pct"] == pytest.approx(10.0)

    # Churn: -0.5 pp
    assert result["churn_rate"]["delta_pp"] == pytest.approx(-0.5)

    # NRR: +3.0 pp
    assert result["nrr"]["delta_pp"] == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# Test 2: negative MRR growth
# ---------------------------------------------------------------------------
def test_mom_deltas_negative_mrr():
    """MRR going down -> negative delta_pct."""
    history = {
        "periods": ["2024-01", "2024-02"],
        "mrr": [1000.0, 900.0],
        "churn_rate": [3.0, 3.5],
        "nrr": [98.0, 95.0],
    }
    result = calculate_mom_deltas(history)

    assert result is not None
    assert result["mrr"]["delta_pct"] == pytest.approx(-10.0)
    assert result["churn_rate"]["delta_pp"] == pytest.approx(0.5)
    assert result["nrr"]["delta_pp"] == pytest.approx(-3.0)


# ---------------------------------------------------------------------------
# Test 3: fewer than 2 → None
# ---------------------------------------------------------------------------
def test_mom_deltas_insufficient_snapshots():
    """One snapshot -> None."""
    history = {
        "periods": ["2024-01"],
        "mrr": [1000.0],
        "churn_rate": [3.5],
        "nrr": [95.0],
    }
    assert calculate_mom_deltas(history) is None


# ---------------------------------------------------------------------------
# Test 4: empty history → None
# ---------------------------------------------------------------------------
def test_mom_deltas_empty():
    """Empty history -> None."""
    assert calculate_mom_deltas({}) is None
    assert calculate_mom_deltas({"periods": []}) is None


# ---------------------------------------------------------------------------
# Test 5: three snapshots → uses last two
# ---------------------------------------------------------------------------
def test_mom_deltas_three_entries():
    """Three entries: uses the last two for delta."""
    history = {
        "periods": ["2023-12", "2024-01", "2024-02"],
        "mrr": [800.0, 1000.0, 1100.0],
        "churn_rate": [4.0, 3.5, 3.0],
        "nrr": [90.0, 95.0, 98.0],
    }
    result = calculate_mom_deltas(history)

    assert result is not None
    assert result["period"]["current"] == "2024-02"
    assert result["period"]["previous"] == "2024-01"
    # Delta between last two: 1000 -> 1100 = +10%
    assert result["mrr"]["delta_pct"] == pytest.approx(10.0)
    assert result["churn_rate"]["delta_pp"] == pytest.approx(-0.5)
    assert result["nrr"]["delta_pp"] == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# Test 6: old_mrr = 0 → delta_pct None
# ---------------------------------------------------------------------------
def test_mom_deltas_zero_old_mrr():
    """When previous MRR is zero, delta_pct should be None (no div by zero)."""
    history = {
        "periods": ["2024-01", "2024-02"],
        "mrr": [0.0, 100.0],
        "churn_rate": [0.0, 0.0],
        "nrr": [0.0, 0.0],
    }
    result = calculate_mom_deltas(history)
    assert result is not None
    assert result["mrr"]["delta_pct"] is None
