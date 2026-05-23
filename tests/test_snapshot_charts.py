"""
test_snapshot_charts.py — Tests for _render_snapshot_charts() (v3.3 Step 9)

Covers:
    - No user_id → info message
    - No history → info message
    - Single period → metric + caption
    - Multiple periods → line_chart called
    - No churn data → info message
"""

import importlib

import pytest
from unittest.mock import MagicMock


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════

_DASHBOARD_MODULE = None


@pytest.fixture(autouse=True)
def _reset_module_cache():
    """Reset the cached dashboard module between tests."""
    global _DASHBOARD_MODULE
    _DASHBOARD_MODULE = None
    yield


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════


def _get_dashboard(mocker):
    """Import app.pages.5_dashboard once, mocking top-level side-effects.

    Also patches get_snapshot_history on the imported module so that
    the local reference inside 5_dashboard is replaced.
    """
    global _DASHBOARD_MODULE
    if _DASHBOARD_MODULE is not None:
        return _DASHBOARD_MODULE
    mocker.patch("streamlit.set_page_config")
    _DASHBOARD_MODULE = importlib.import_module("app.pages.5_dashboard")
    # Replace local reference to get_snapshot_history with a MagicMock
    _DASHBOARD_MODULE.get_snapshot_history = MagicMock(
        return_value=None,
        name="get_snapshot_history",
    )
    return _DASHBOARD_MODULE


def _set_history(history=None):
    """Configure the mocked get_snapshot_history return value."""
    global _DASHBOARD_MODULE
    if _DASHBOARD_MODULE is not None:
        _DASHBOARD_MODULE.get_snapshot_history.return_value = history


def _patch_session_state(mocker, user_id=None, currency="USD"):
    """Mock st.session_state with optional user_id."""
    import streamlit as st
    mock_state = {"user_id": user_id, "currency": currency}
    mocker.patch.object(st, "session_state", mock_state)


# ══════════════════════════════════════════════════════════════════════════════
# Test 1: No user_id → info message
# ══════════════════════════════════════════════════════════════════════════════

def test_no_user_id_shows_info(mocker):
    """When not signed in, show info message and return early."""
    _patch_session_state(mocker, user_id=None)

    mock_info = mocker.patch("streamlit.info")
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.markdown")

    mod = _get_dashboard(mocker)
    mod._render_snapshot_charts()

    mock_info.assert_called_once()
    assert "Sign in" in mock_info.call_args[0][0]


# ══════════════════════════════════════════════════════════════════════════════
# Test 2: No history → info message
# ══════════════════════════════════════════════════════════════════════════════

def test_no_history_shows_info(mocker):
    """When no snapshot history exists, show info."""
    _patch_session_state(mocker, user_id="u1")
    _get_dashboard(mocker)
    _set_history(None)

    mock_info = mocker.patch("streamlit.info")
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.markdown")

    _DASHBOARD_MODULE._render_snapshot_charts()

    mock_info.assert_called_once()
    assert "No historical snapshots" in mock_info.call_args[0][0]


# ══════════════════════════════════════════════════════════════════════════════
# Test 3: Single period → metric + caption for MRR
# ══════════════════════════════════════════════════════════════════════════════

def test_single_period_shows_metric_and_caption(mocker):
    """With one snapshot, show metric (not line_chart) and caption for both MRR & Churn."""
    _patch_session_state(mocker, user_id="u1")
    _get_dashboard(mocker)
    _set_history({
        "periods": ["2024-01"],
        "mrr": [1000.0],
        "churn_rate": [3.5],
    })

    mock_metric = mocker.patch("streamlit.metric")
    mock_line_chart = mocker.patch("streamlit.line_chart")
    mock_caption = mocker.patch("streamlit.caption")
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.markdown")
    mocker.patch("streamlit.info")

    _DASHBOARD_MODULE._render_snapshot_charts()

    # No line_chart calls
    assert mock_line_chart.call_count == 0
    # metric called for MRR and Churn Rate
    assert mock_metric.call_count == 2
    # Caption called twice (one for MRR, one for churn)
    assert mock_caption.call_count == 2


# ══════════════════════════════════════════════════════════════════════════════
# Test 4: Multiple periods → line_chart called
# ══════════════════════════════════════════════════════════════════════════════

def test_multiple_periods_calls_line_chart(mocker):
    """With 2+ snapshots, line_chart should be called for both MRR and churn."""
    _patch_session_state(mocker, user_id="u1")
    _get_dashboard(mocker)
    _set_history({
        "periods": ["2024-01", "2024-02", "2024-03"],
        "mrr": [1000.0, 1100.0, 1200.0],
        "churn_rate": [3.5, 3.0, 2.5],
    })

    mock_line_chart = mocker.patch("streamlit.line_chart")
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.markdown")
    mocker.patch("streamlit.metric")

    _DASHBOARD_MODULE._render_snapshot_charts()

    # line_chart called twice: MRR and Churn Rate
    assert mock_line_chart.call_count == 2


# ══════════════════════════════════════════════════════════════════════════════
# Test 5: No churn data → info message for churn
# ══════════════════════════════════════════════════════════════════════════════

def test_no_churn_data_shows_info(mocker):
    """When churn_rate list is empty, show info for churn section."""
    _patch_session_state(mocker, user_id="u1")
    _get_dashboard(mocker)
    _set_history({
        "periods": ["2024-01", "2024-02"],
        "mrr": [1000.0, 1100.0],
        "churn_rate": [],
    })

    mock_info = mocker.patch("streamlit.info")
    mock_line_chart = mocker.patch("streamlit.line_chart")
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.markdown")

    _DASHBOARD_MODULE._render_snapshot_charts()

    # MRR chart still called
    assert mock_line_chart.call_count == 1
    # Churn info called
    assert any("No churn rate data" in c[0][0] for c in mock_info.call_args_list)