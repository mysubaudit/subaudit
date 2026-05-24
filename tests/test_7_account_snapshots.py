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


# ═══════════════════════════════════════════════════════════════
# v3.3.5 — Step 12: CSV export tests
# ═══════════════════════════════════════════════════════════════

class TestBuildSnapshotCsv:
    """Tests for _build_snapshot_csv() — CSV generation from history dict."""

    def test_csv_has_period_first_and_skips_service_keys(self, mocker):
        """periods column first, no snapshot_id/user_id/created_at/source."""
        mocker.patch("streamlit.set_page_config")
        mod = importlib.import_module("app.pages.7_account")

        history = {
            "periods":     ["2026-04", "2026-05"],
            "mrr":         [1000.0, 1200.0],
            "churn_rate":  [0.05, 0.03],
            "snapshot_id": ["id1", "id2"],
            "user_id":     ["u1", "u1"],
            "created_at":  ["2026-01-01", "2026-02-01"],
            "source":      ["f1.csv", "f2.csv"],
        }

        csv_str = mod._build_snapshot_csv(history)
        lines = csv_str.strip().split("\r\n")

        # Header: periods first, then mrr, churn_rate (alphabetically after period)
        header = lines[0].split(",")
        assert header[0] == "periods"
        assert "snapshot_id" not in header
        assert "user_id" not in header
        assert "created_at" not in header
        assert "source" not in header
        assert "mrr" in header
        assert "churn_rate" in header

        # Data rows
        row1 = lines[1].split(",")
        assert row1[0] == "2026-04"
        row2 = lines[2].split(",")
        assert row2[0] == "2026-05"

    def test_csv_handles_none_values(self, mocker):
        """None values become empty strings."""
        mocker.patch("streamlit.set_page_config")
        mod = importlib.import_module("app.pages.7_account")

        history = {
            "periods": ["2026-04"],
            "mrr":     [None],
            "arpu":    [50.0],
        }

        csv_str = mod._build_snapshot_csv(history)
        lines = csv_str.strip().split("\r\n")
        row1 = lines[1].split(",")
        # mrr is None → empty string
        mrr_idx = lines[0].split(",").index("mrr")
        assert row1[mrr_idx] == ""

    def test_csv_empty_history_returns_header_only(self, mocker):
        """Empty period list → header row, no data."""
        mocker.patch("streamlit.set_page_config")
        mod = importlib.import_module("app.pages.7_account")

        history = {"periods": [], "mrr": []}
        csv_str = mod._build_snapshot_csv(history)
        lines = csv_str.strip().split("\r\n")
        assert len(lines) == 1  # header only


class TestRenderSnapshotExport:
    """Tests for _render_snapshot_export() — download button."""

    def test_download_button_called_with_csv(self, mocker):
        """_render_snapshot_export calls st.download_button with correct args."""
        mocker.patch("streamlit.set_page_config")
        mod = importlib.import_module("app.pages.7_account")

        mock_download = mocker.patch("streamlit.download_button")

        history = {"periods": ["2026-04"], "mrr": [1000.0]}
        mod._render_snapshot_export(history)

        mock_download.assert_called_once()
        _, kwargs = mock_download.call_args
        assert kwargs["label"] == "📥 Export history as CSV"
        assert kwargs["file_name"] == "snapshots_history.csv"
        assert kwargs["mime"] == "text/csv"
        assert "periods" in kwargs["data"]

    def test_download_button_free_for_all_plans(self, mocker):
        """Help text mentions 'Free for all plans'."""
        mocker.patch("streamlit.set_page_config")
        mod = importlib.import_module("app.pages.7_account")

        mock_download = mocker.patch("streamlit.download_button")

        mod._render_snapshot_export({"periods": ["2026-04"], "mrr": [100.0]})

        _, kwargs = mock_download.call_args
        assert "Free for all plans" in kwargs["help"]


class TestSnapshotsSectionWithExport:
    """Integration: _render_snapshots_section includes export button."""

    def test_export_called_when_history_present(self, mocker):
        """When history exists, _render_snapshot_export is invoked."""
        get_history_mock = _patch_account(
            mocker, user_id="u5",
            history={"periods": ["2026-04"], "mrr": [1000.0]},
        )

        mock_download = mocker.patch("streamlit.download_button")

        importlib.invalidate_caches()
        mod = _import_account(mocker)
        mod._render_snapshots_section()

        # download_button should be called (via _render_snapshot_export)
        mock_download.assert_called_once()
        get_history_mock.assert_called_once_with("u5")

    def test_export_not_called_when_no_history(self, mocker):
        """When no history, download_button is not called."""
        _patch_account(mocker, user_id="u6", history=None)

        mock_download = mocker.patch("streamlit.download_button")

        importlib.invalidate_caches()
        mod = _import_account(mocker)
        mod._render_snapshots_section()

        # download_button should NOT be called — early return
        mock_download.assert_not_called()