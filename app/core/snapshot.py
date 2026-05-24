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
    Compute month-over-month delta from snapshot history.

    Parameters
    ----------
    history : dict
        Output from get_snapshot_history(), keys: periods, mrr, churn_rate, nrr.

    Returns
    -------
    dict | None
        {
            "period": {"current": "YYYY-MM", "previous": "YYYY-MM"},
            "mrr": {"current": float, "previous": float, "delta_pct": float|None},
            "churn_rate": {"current": float, "previous": float, "delta_pp": float},
            "nrr": {"current": float, "previous": float, "delta_pp": float},
        }
        None if fewer than 2 periods.

    Behavior
    --------
    - Requires at least 2 periods. Returns None otherwise.
    - MRR delta is percentage: (cur - prev) / prev * 100. None if prev == 0.
    - Churn/NRR deltas are in percentage points: cur - prev.
    - Uses last two periods in history.
    """
    periods = history.get("periods") or history.get("period")
    if not periods or len(periods) < 2:
        return None

    mrr_list = history.get("mrr", [])
    churn_list = history.get("churn_rate", [])
    nrr_list = history.get("nrr", [])

    if not mrr_list or len(mrr_list) < 2:
        return None

    # Последние два периода
    prev_mrr = mrr_list[-2]
    cur_mrr = mrr_list[-1]

    prev_churn = _safe_get(churn_list, -2)
    cur_churn = _safe_get(churn_list, -1)
    prev_nrr = _safe_get(nrr_list, -2)
    cur_nrr = _safe_get(nrr_list, -1)

    # MRR delta %
    if prev_mrr and prev_mrr != 0:
        delta_pct = ((cur_mrr - prev_mrr) / prev_mrr) * 100
    else:
        delta_pct = None

    # Churn/NRR delta в pp
    delta_churn = (cur_churn - prev_churn) if (cur_churn is not None and prev_churn is not None) else None
    delta_nrr = (cur_nrr - prev_nrr) if (cur_nrr is not None and prev_nrr is not None) else None

    return {
        "period": {
            "current": periods[-1],
            "previous": periods[-2],
        },
        "mrr": {
            "current": cur_mrr,
            "previous": prev_mrr,
            "delta_pct": delta_pct,
        },
        "churn_rate": {
            "current": cur_churn,
            "previous": prev_churn,
            "delta_pp": delta_churn,
        },
        "nrr": {
            "current": cur_nrr,
            "previous": prev_nrr,
            "delta_pp": delta_nrr,
        },
    }


def _safe_get(lst: list, idx: int):
    """Return element or None if out of range or None."""
    try:
        return lst[idx]
    except (IndexError, TypeError):
        return None
