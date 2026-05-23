"""
test_snapshot.py — Tests for save_snapshot() (v3.3 Step 4)

Covers 4 cases from docs/v3.3_plan.md:
    - Successful save → True
    - Duplicate (same user_id + period) → upsert update → True
    - Supabase error → False, log_warning called
    - Unauthorized user (empty user_id) → False
"""

import pytest
from unittest.mock import MagicMock

_TEST_USER_ID = "550e8400-e29b-41d4-a716-446655440000"
_TEST_PERIOD = "2025-01"

_VALID_METRICS = {
    "mrr": 5000.0,
    "arr": 60000.0,
    "arpu": 100.0,
    "churn_rate": 3.5,
    "nrr": 95.0,
    "ltv": 2800.0,
    "active_subscribers": 50,
    "total_revenue": 120000.0,
}


# ---------------------------------------------------------------------------
# Test 1: Successful save → True
# ---------------------------------------------------------------------------

def test_save_snapshot_success(mocker):
    """
    Successful save of a new snapshot should return True.
    supabase.table("snapshots").upsert(...).execute() is called exactly once.
    """
    mock_table = MagicMock()
    mock_table.upsert.return_value = mock_table
    mock_table.execute.return_value = MagicMock()

    mock_supabase = MagicMock()
    mock_supabase.table.return_value = mock_table

    mocker.patch("app.core.snapshot.log_warning")
    mocker.patch(
        "app.auth.supabase_auth.supabase",
        mock_supabase,
    )

    from app.core.snapshot import save_snapshot

    result = save_snapshot(
        user_id=_TEST_USER_ID,
        metrics=_VALID_METRICS,
        period=_TEST_PERIOD,
        source="test.csv",
    )

    assert result is True

    # Check upsert was called with correct args
    mock_supabase.table.assert_called_once_with("snapshots")
    mock_table.upsert.assert_called_once()

    args, kwargs = mock_table.upsert.call_args
    row = args[0] if args else kwargs

    assert isinstance(row, dict)
    assert row["user_id"] == _TEST_USER_ID
    assert row["period"] == _TEST_PERIOD
    assert row["source"] == "test.csv"
    assert row["mrr"] == 5000.0
    assert row["active_subscribers"] == 50

    assert kwargs.get("on_conflict") == "user_id,period"


# ---------------------------------------------------------------------------
# Test 2: Duplicate → upsert update → True
# ---------------------------------------------------------------------------

def test_save_snapshot_duplicate_upsert(mocker):
    """
    If snapshot for same user_id + period exists, perform UPDATE (upsert), not INSERT.
    Should return True (no error).
    """
    mock_table = MagicMock()
    mock_table.upsert.return_value = mock_table
    mock_table.execute.return_value = MagicMock()

    mock_supabase = MagicMock()
    mock_supabase.table.return_value = mock_table

    mocker.patch("app.core.snapshot.log_warning")
    mocker.patch(
        "app.auth.supabase_auth.supabase",
        mock_supabase,
    )

    from app.core.snapshot import save_snapshot

    result1 = save_snapshot(
        user_id=_TEST_USER_ID,
        metrics=_VALID_METRICS,
        period=_TEST_PERIOD,
        source="file1.csv",
    )
    assert result1 is True

    updated_metrics = {**_VALID_METRICS, "mrr": 5500.0}
    result2 = save_snapshot(
        user_id=_TEST_USER_ID,
        metrics=updated_metrics,
        period=_TEST_PERIOD,
        source="file2.csv",
    )
    assert result2 is True

    assert mock_table.upsert.call_count == 2

    second_call_args = mock_table.upsert.call_args_list[1]
    args2, kwargs2 = second_call_args
    row2 = args2[0] if args2 else kwargs2
    assert row2["mrr"] == 5500.0


# ---------------------------------------------------------------------------
# Test 3: Supabase error → False, log_warning called
# ---------------------------------------------------------------------------

def test_save_snapshot_supabase_error(mocker):
    """
    On Supabase error:
    - Returns False (does NOT crash).
    - log_warning() is called.
    """
    mock_table = MagicMock()
    mock_table.upsert.return_value = mock_table
    mock_table.execute.side_effect = Exception("Supabase connection error")

    mock_supabase = MagicMock()
    mock_supabase.table.return_value = mock_table

    mock_log_warning = mocker.patch("app.core.snapshot.log_warning")
    mocker.patch(
        "app.auth.supabase_auth.supabase",
        mock_supabase,
    )

    from app.core.snapshot import save_snapshot

    result = save_snapshot(
        user_id=_TEST_USER_ID,
        metrics=_VALID_METRICS,
        period=_TEST_PERIOD,
    )

    assert result is False

    mock_log_warning.assert_called_once()

    call_args = mock_log_warning.call_args
    message = call_args[0][0] if call_args[0] else ""
    assert "save_snapshot_failed" in message


# ---------------------------------------------------------------------------
# Test 4: Unauthorized user → False
# ---------------------------------------------------------------------------

def test_save_snapshot_unauthorized_user(mocker):
    """
    Empty or whitespace user_id → returns False.
    Supabase must NOT be called.
    """
    mock_supabase = MagicMock()
    mocker.patch("app.core.snapshot.log_warning")
    mocker.patch(
        "app.auth.supabase_auth.supabase",
        mock_supabase,
    )

    from app.core.snapshot import save_snapshot

    result1 = save_snapshot(
        user_id="",
        metrics=_VALID_METRICS,
        period=_TEST_PERIOD,
    )
    assert result1 is False

    result2 = save_snapshot(
        user_id="   ",
        metrics=_VALID_METRICS,
        period=_TEST_PERIOD,
    )
    assert result2 is False

    mock_supabase.table.assert_not_called()


# ---------------------------------------------------------------------------
# Test 5: Empty period → False
# ---------------------------------------------------------------------------

def test_save_snapshot_empty_period(mocker):
    """
    Empty period → returns False.
    Supabase must NOT be called.
    """
    mock_supabase = MagicMock()
    mocker.patch("app.core.snapshot.log_warning")
    mocker.patch(
        "app.auth.supabase_auth.supabase",
        mock_supabase,
    )

    from app.core.snapshot import save_snapshot

    result = save_snapshot(
        user_id=_TEST_USER_ID,
        metrics=_VALID_METRICS,
        period="",
    )
    assert result is False

    mock_supabase.table.assert_not_called()