"""
tests/test_7_account_snapshots.py
v3.3, Step 11 — Tests for _render_snapshots_section() on Account page.
"""
import importlib
from unittest.mock import MagicMock

import pytest

# We import 5_dashboard-style lazy imports — mock streamlit early.
def _import_account(mocker):
    """Import app.pages.7_account, mocking st.set_page_config top-level call."""
    mocker.patch("streamlit.set_page_config")
    return importlib.import_module("app.pages.7_account")


# ───────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────

def _patch_account(mocker, user_id=None, history=None):
    """Configure session state + get_snapshot_history mock."""
    import streamlit as st
    state = {"user_email": "u@u.com", "user_plan": "free"}
    if user_id:
        state["user_id"] = user_id
    mocker.patch.object(st, "session_state", state)

    # Patch get_snapshot_history globally in snapshot module
    mock = MagicMock(return_value=history)
    mocker.patch("app.core.snapshot.get_snapshot_history", mock)
    return mock


# ═══════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════

def test_no_user_id_shows_signin_info(mocker):
    """When user_id is missing, show info and return early."""
    _patch_account(mocker, user_id=None)

    # patch st.* used inside _render_snapshots_section
    mock_divider = mocker.patch("streamlit.divider")
    mock_subheader = mocker.patch("streamlit.subheader")
    mock_info = mocker.patch("streamlit.info")

    mod = _import_account(mocker)
    mod._render_snapshots_section()

    mock_info.assert_called_once_with("Sign in to see your saved snapshots.")


def test_no_history_shows_empty_info(mocker):
    """No snapshots → info message, no dataframe."""
    get_history_mock = _patch_account(mocker, user_id="u1", history=None)

    mock_divider = mocker.patch("streamlit.divider")
    mock_info = mocker.patch("streamlit.info")
    mock_dataframe = mocker.patch("streamlit.dataframe")

    mod = _import_account(mocker)
    mod._render_snapshots_section()

    mock_info.assert_called_once()
    assert "will appear here" in mock_info.call_args[0][0]
    mock_dataframe.assert_not_called()
    get_history_mock.assert_called_once_with("u1")


def test_history_with_periods_renders_dataframe(mocker):
    """History present → render dataframe with correct columns."""
    history = {
        "periods":     ["2026-04", "2026-05"],
        "mrr":         [1000.0,   1200.0],
        "arpu":        [50.0,     None],
        "churn_rate":  [0.05,     0.03],
        "nrr":         [1.1,      0.95],
    }
    get_history_mock = _patch_account(mocker, user_id="u2", history=history)

    mock_divider = mocker.patch("streamlit.divider")
    mock_subheader = mocker.patch("streamlit.subheader")
    mock_info = mocker.patch("streamlit.info")
    mock_dataframe = mocker.patch("streamlit.dataframe")
    mock_caption = mocker.patch("streamlit.caption")

    mod = _import_account(mocker)
    mod._render_snapshots_section()

    # info should not be called
    mock_info.assert_not_called()
    # dataframe called once
    mock_dataframe.assert_called_once()
    df_arg = mock_dataframe.call_args[0][0]
    assert df_arg["Period"] == ["2026-04", "2026-05"]
    assert df_arg["MRR ($)"] == ["$1,000.00", "$1,200.00"]
    assert df_arg["ARPU ($)"] == ["$50.00", "—"]
    assert df_arg["Churn"] == ["5.00%", "3.00%"]
    assert df_arg["NRR"] == ["110.00%", "95.00%"]
    mock_caption.assert_called_once_with("2 snapshot(s) saved.")
    get_history_mock.assert_called_once_with("u2")


def test_empty_periods_list_shows_info(mocker):
    """periods list exists but is empty → show info."""
    _patch_account(mocker, user_id="u3", history={"periods": []})

    mock_info = mocker.patch("streamlit.info")
    mock_dataframe = mocker.patch("streamlit.dataframe")

    mod = _import_account(mocker)
    mod._render_snapshots_section()

    mock_info.assert_called_once()
    mock_dataframe.assert_not_called()


def test_periods_key_missing_shows_info(mocker):
    """history dict without 'periods' key → treat same as no history."""
    _patch_account(mocker, user_id="u4", history={"mrr": [100]})

    mock_info = mocker.patch("streamlit.info")
    mock_dataframe = mocker.patch("streamlit.dataframe")

    mod = _import_account(mocker)
    mod._render_snapshots_section()

    mock_info.assert_called_once()
    mock_dataframe.assert_not_called()