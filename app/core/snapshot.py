"""
core/snapshot.py
SubAudit v3.3 — Snapshot History
Step 3: save_snapshot() — save metrics to Supabase

Saves aggregated metrics (NOT raw CSV) into the snapshots table.
One snapshot per user per month (UNIQUE user_id, period).
On duplicate: UPDATE (upsert), not INSERT.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.observability.logger import log_warning


# ---------------------------------------------------------------------------
# Constants — metric keys to store
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# save_snapshot()
# ---------------------------------------------------------------------------

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
    row["created_at"] = datetime.now(timezone.utc).isoformat()

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