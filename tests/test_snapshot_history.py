"""
test_snapshot_history.py — Tests for get_snapshot_history() (v3.3 Step 7)

Covers 4 cases from docs/v3.3_plan.md:
    - User with history → correct dict
    - New user without history → None
    - Correct sort order by period (ASC)
    - Supabase error → None + log_warning
"""

import pytest
from unittest.mock import MagicMock

_TEST_USER_ID = "550e8400-e29b-41d4-a716-446655440000"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_supabase(mocker, response_data):
    """Build a mock Supabase chain for get_snapshot_history()."""
    mock_response = MagicMock()
    mock_response.data = response_data

    mock_query = MagicMock()
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.execute.return_value = mock_response

    mock_table = MagicMock()
    mock_table.select.return_value = mock_query

    mock_supabase = MagicMock()
    mock_supabase.table.return_value = mock_table

    mocker.patch("app.core.snapshot.log_warning")
    mocker.patch("app.auth.supabase_auth.supabase", mock_supabase)

    return mock_supabase, mock_query


# ---------------------------------------------------------------------------
# Test 1: User with history → correct dict
# ---------------------------------------------------------------------------

def test_history_with_data(mocker):
    """User with snapshot history → returns correct dict."""
    response_data = [
        {
            "snapshot_id": "id1",
            "user_id": _TEST_USER_ID,
            "period": "2024-01",
            "mrr": 1000.0,
            "churn_rate": 3.5,
            "nrr": 95.0,
            "active_subscribers": 50,
        },
        {
            "snapshot_id": "id2",
            "user_id": _TEST_USER_ID,
            "period": "2024-02",
            "mrr": 1100.0,
            "churn_rate": 3.0,
            "nrr": 98.0,
            "active_subscribers": 55,
        },
    ]

    _make_mock_supabase(mocker, response_data)

    from app.core.snapshot import get_snapshot_history

    result = get_snapshot_history(_TEST_USER_ID)

    assert result is not None
    assert "periods" in result
    assert result["periods"] == ["2024-01", "2024-02"]
    assert result["mrr"] == [1000.0, 1100.0]
    assert result["churn_rate"] == [3.5, 3.0]
    assert result["nrr"] == [95.0, 98.0]
    assert result["active_subscribers"] == [50, 55]


# ---------------------------------------------------------------------------
# Test 2: Empty history → None
# ---------------------------------------------------------------------------

def test_no_history_returns_none(mocker):
    """Empty data list → returns None (no history)."""
    _make_mock_supabase(mocker, [])

    from app.core.snapshot import get_snapshot_history

    result = get_snapshot_history(_TEST_USER_ID)
    assert result is None


# ---------------------------------------------------------------------------
# Test 3: Correct sort order by period (ASC)
# ---------------------------------------------------------------------------

def test_order_by_period_asc(mocker):
    """Query must use .order('period', desc=False)."""
    _, mock_query = _make_mock_supabase(
        mocker,
        [{"snapshot_id": "id1", "user_id": _TEST_USER_ID, "period": "2024-01", "mrr": 1000.0}],
    )

    from app.core.snapshot import get_snapshot_history

    get_snapshot_history(_TEST_USER_ID)

    mock_query.order.assert_called_once_with("period", desc=False)


# ---------------------------------------------------------------------------
# Test 4: Supabase error → None, log_warning called
# ---------------------------------------------------------------------------

def test_supabase_error_returns_none(mocker):
    """Supabase exception → returns None, log_warning called."""
    mock_query = MagicMock()
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.execute.side_effect = Exception("Connection timed out")

    mock_table = MagicMock()
    mock_table.select.return_value = mock_query

    mock_supabase = MagicMock()
    mock_supabase.table.return_value = mock_table

    mock_log = mocker.patch("app.core.snapshot.log_warning")
    mocker.patch("app.auth.supabase_auth.supabase", mock_supabase)

    from app.core.snapshot import get_snapshot_history

    result = get_snapshot_history(_TEST_USER_ID)

    assert result is None
    mock_log.assert_called_once()
    assert "get_snapshot_history_failed" in mock_log.call_args[0][0]