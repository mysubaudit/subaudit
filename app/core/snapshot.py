"""
core/snapshot.py
SubAudit v3.3 — Snapshot History
Step 3: save_snapshot() — save metrics to Supabase
Step 6: get_snapshot_history() — load history from Supabase

Saves aggregated metrics (NOT raw CSV) into the snapshots table.
One snapshot per user per month (UNIQUE user_id, period).
On duplicate: UPDATE (upsert), not INSERT.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.observability.logger import log_warning


# --------------------------------------------------------------------------
# Constants — metric keys to store
# --------------------------------------------------------------------------

_SNAPSHOT_METRIC_KEYS = [
    "mrr",
    "arr",
    "arpu",
    "churn_rate",
    "nrr",
    "ltv",
    "active_subscribers",
    "total_revenue",
]


# --------------------------------------------------------------------------
# save_snapshot()
# --------------------------------------------------------------------------

def save_snapshot(
    user_id: str,
    metrics: dict,
    period: str,
    source: str = "",
) -> bool:
    """
    Save a metrics snapshot into the snapshots table (Supabase).

    Parameters
    ----------
    user_id : str
        User UUID from Supabase Auth.
    metrics : dict
        Metrics dictionary from get_all_metrics().
    period : str
        Period in 'YYYY-MM' format (calendar month).
    source : str
        Uploaded CSV file name (optional).

    Returns
    -------
    bool
        True — snapshot saved/updated successfully.
        False — error (unauthorised user, Supabase error).

    Behavior
    --------
    - If user_id is empty → False (unauthorised).
    - Upsert with ON CONFLICT (user_id, period) DO UPDATE.
    - On Supabase error: log_warning(), return False, do NOT crash.
    """
    # Unauthorised user
    if not user_id or not user_id.strip():
        return False

    if not period or not period.strip():
        return False

    # Pick only the required metric keys
    row = {
        key: metrics.get(key)
        for key in _SNAPSHOT_METRIC_KEYS
        if key in metrics
    }

    # Add service fields
    row["user_id"] = user_id
    row["period"] = period
    row["source"] = source
    # created_at is handled by Supabase (TIMESTAMPTZ DEFAULT NOW())

    try:
        # Import supabase client from auth module
        # (tests mock app.auth.supabase_auth.supabase)
        from app.auth.supabase_auth import supabase as sb_client

        if sb_client is None:
            log_warning(
                "save_snapshot_no_client",
                extra={"user_id": user_id, "period": period},
            )
            return False

        # upsert: if (user_id, period) already exists → update the row
        sb_client.table("snapshots").upsert(
            row,
            on_conflict="user_id,period",
        ).execute()

        return True

    except Exception as exc:
        log_warning(
            "save_snapshot_failed",
            extra={
                "user_id": user_id,
                "period": period,
                "error": str(exc),
                "exc_type": type(exc).__name__,
            },
        )
        return False


# --------------------------------------------------------------------------
# get_snapshot_history()
# --------------------------------------------------------------------------

def get_snapshot_history(user_id: str) -> dict | None:
    """
    Get snapshot history for a user from Supabase.

    Parameters
    ----------
    user_id : str
        User UUID from Supabase Auth.

    Returns
    -------
    dict | None
        - dict: snapshot history, keys are metric names, values are lists.
        - None: no history found or an error occurred.

    Example output
    --------------
    {
        "periods": ["2023-01", "2023-02", "2023-03"],
        "mrr": [1000, 1100, 1200],
        "churn_rate": [0.05, 0.04, 0.045],
        ...
    }
    """
    if not user_id or not user_id.strip():
        return None

    try:
        from app.auth.supabase_auth import supabase as sb_client

        if sb_client is None:
            log_warning(
                "get_snapshot_history_no_client",
                extra={"user_id": user_id},
            )
            return None

        # SELECT *, order by period ASC
        query = (
            sb_client.table("snapshots")
            .select("*")
            .eq("user_id", user_id)
            .order("period", desc=False)
        )
        response = query.execute()

        # No history or empty list
        if not response.data:
            return None

        # Transform list of dicts (rows) to dict of lists (columns)
        history = {key: [] for key in response.data[0]}
        for row in response.data:
            for key, value in row.items():
                history[key].append(value)

        # Rename 'period' to 'periods' for clarity
        if "period" in history:
            history["periods"] = history.pop("period")

        return history

    except Exception as exc:
        log_warning(
            "get_snapshot_history_failed",
            extra={
                "user_id": user_id,
                "error": str(exc),
                "exc_type": type(exc).__name__,
            },
        )
        return None
# --------------------------------------------------------------------------
# calculate_mom_deltas()
# --------------------------------------------------------------------------

def calculate_mom_deltas(history: dict) -> dict | None:
    """
    Calculate Month-over-Month deltas from snapshot history.

    Parameters
    ----------
    history : dict
        Snapshot history from get_snapshot_history().

    Returns
    -------
    dict | None
        {
            "mrr": {"current": 1100, "previous": 1000, "delta_pct": 10.0},
            "churn_rate": {"current": 3.0, "previous": 3.5, "delta_pp": -0.5},
            "nrr": {"current": 98.0, "previous": 95.0, "delta_pp": 3.0},
            "period": {"current": "2024-02", "previous": "2024-01"},
        }
        Returns None if history has fewer than 2 snapshots.
    """
    if not history or len(history.get("periods", [])) < 2:
        return None

    periods = history["periods"]
    last = len(periods) - 1
    prev = last - 1

    result: dict = {"period": {"current": periods[last], "previous": periods[prev]}}

    # MRR — relative percentage change
    old_mrr = history.get("mrr", [None] * len(periods))[prev]
    new_mrr = history.get("mrr", [None] * len(periods))[last]
    result["mrr"] = {
        "current": new_mrr,
        "previous": old_mrr,
        "delta_pct": ((new_mrr - old_mrr) / abs(old_mrr)) * 100
        if old_mrr is not None and old_mrr != 0
        else None,
    }

    # Churn Rate — absolute percentage-point change
    old_churn = history.get("churn_rate", [None] * len(periods))[prev]
    new_churn = history.get("churn_rate", [None] * len(periods))[last]
    result["churn_rate"] = {
        "current": new_churn,
        "previous": old_churn,
        "delta_pp": (new_churn - old_churn)
        if old_churn is not None and new_churn is not None
        else None,
    }

    # NRR — absolute percentage-point change
    old_nrr = history.get("nrr", [None] * len(periods))[prev]
    new_nrr = history.get("nrr", [None] * len(periods))[last]
    result["nrr"] = {
        "current": new_nrr,
        "previous": old_nrr,
        "delta_pp": (new_nrr - old_nrr)
        if old_nrr is not None and new_nrr is not None
        else None,
    }

    return result

# --------------------------------------------------------------------------
# calculate_mom_deltas()
# --------------------------------------------------------------------------

def calculate_mom_deltas(history: dict) -> dict | None:
    """
    Calculate Month-over-Month deltas from snapshot history.

    Returns None if history has fewer than 2 snapshots.
    """
    if not history or len(history.get("periods", [])) < 2:
        return None

    periods = history["periods"]
    last_idx = len(periods) - 1
    prev_idx = last_idx - 1

    result: dict = {"period": {"current": periods[last_idx], "previous": periods[prev_idx]}}

    # MRR
    mrr_list = history.get("mrr", [])
    old_mrr = mrr_list[prev_idx] if len(mrr_list) > prev_idx else None
    new_mrr = mrr_list[last_idx] if len(mrr_list) > last_idx else None
    result["mrr"] = {
        "current": new_mrr,
        "previous": old_mrr,
        "delta_pct": ((new_mrr - old_mrr) / abs(old_mrr)) * 100
        if old_mrr is not None and old_mrr != 0
        else None,
    }

    # Churn Rate
    churn_list = history.get("churn_rate", [])
    old_churn = churn_list[prev_idx] if len(churn_list) > prev_idx else None
    new_churn = churn_list[last_idx] if len(churn_list) > last_idx else None
    result["churn_rate"] = {
        "current": new_churn,
        "previous": old_churn,
        "delta_pp": (new_churn - old_churn)
        if old_churn is not None and new_churn is not None
        else None,
    }

    # NRR
    nrr_list = history.get("nrr", [])
    old_nrr = nrr_list[prev_idx] if len(nrr_list) > prev_idx else None
    new_nrr = nrr_list[last_idx] if len(nrr_list) > last_idx else None
    result["nrr"] = {
        "current": new_nrr,
        "previous": old_nrr,
        "delta_pp": (new_nrr - old_nrr)
        if old_nrr is not None and new_nrr is not None
        else None,
    }

    return result
