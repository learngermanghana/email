"""Helper functions for computing leaderboards from the scores sheet."""

from __future__ import annotations

import re
from datetime import datetime

import pandas as pd

def _canon_assignment(s: str | None) -> str:
    """
    Canonicalize assignment names so duplicates match:
    - lowercase, strip spaces
    - normalize dashes
    - strip leading level tag like "A1", "B1", ...
    """
    if not isinstance(s, str):
        return ""
    x = s.strip().lower()
    x = x.replace("–", "-").replace("—", "-")
    x = re.sub(r"\s+", " ", x)
    x = re.sub(r"^(a1|a2|b1|b2|c1|c2)\s+", "", x)
    return x

def _dedupe_latest_attempt(scores_df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep only the best attempt per (StudentCode, AssignmentKey).
    Prefer higher scores; break score ties by the most recent date.
    """
    tmp = scores_df.copy()
    tmp["_AssignmentKey"] = tmp["Assignment"].apply(_canon_assignment)

    # Order so that the last row per group is the preferred attempt:
    #   1) by Score ascending (highest score is last)
    #   2) by Date ascending (latest is last when scores tie)
    tmp = tmp.sort_values(["Score", "Date"], ascending=[True, True])

    keep_idx = tmp.groupby(["StudentCode", "_AssignmentKey"], dropna=False).tail(1).index
    kept = tmp.loc[keep_idx].drop(columns=["_AssignmentKey"])
    return kept

def compute_level_list(scores_df: pd.DataFrame) -> list[str]:
    """Return the sorted list of non-empty level codes present in *scores_df*."""
    if "Level" not in scores_df.columns:
        return []

    levels = (
        scores_df["Level"]
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .str.upper()
        .unique()
    )
    return sorted(levels.tolist())

def compute_leaderboard(
    scores_df: pd.DataFrame,
    *,
    level: str | None,
    start: datetime | pd.Timestamp | None = None,
    end: datetime | pd.Timestamp | None = None,
    search: str | None = None,
    min_assignments: int | None = None,
) -> pd.DataFrame:
    """Aggregate leaderboard stats for *scores_df* applying optional filters."""

    column_order = [
        "Rank",
        "Student",
        "StudentCode",
        "Level",
        "TotalMarks",
        "AssignmentsCompleted",
        "AverageScore",
        "LastActivity",
    ]

    df = scores_df.copy()

    if df.empty:
        return pd.DataFrame(columns=column_order)

    # Normalize filters
    level_filter = level.upper() if level else None
    start_ts = pd.to_datetime(start) if start is not None else None
    end_ts = pd.to_datetime(end) if end is not None else None
    search_term = search.strip() if isinstance(search, str) else ""

    if level_filter:
        df = df[df["Level"].astype(str).str.upper() == level_filter]

    if start_ts is not None:
        df = df[df["Date"] >= start_ts]

    if end_ts is not None:
        df = df[df["Date"] < end_ts]

    if search_term:
        escaped = re.escape(search_term)
        name_match = df["Name"].astype(str).str.contains(escaped, case=False, na=False, regex=True)
        code_match = df["StudentCode"].astype(str).str.contains(escaped, case=False, na=False, regex=True)
        df = df[name_match | code_match]

    if df.empty:
        return pd.DataFrame(columns=column_order)

    # Deduplicate multiple attempts of same assignment
    kept = _dedupe_latest_attempt(df)

    if kept.empty:
        return pd.DataFrame(columns=column_order)

    # Aggregate per student
    base = kept.copy()
    base["_AssignmentKey"] = base["Assignment"].apply(_canon_assignment)

    # distinct assignments completed
    completed = (
        base.groupby("StudentCode")["_AssignmentKey"]
        .nunique()
        .rename("AssignmentsCompleted")
    )

    agg = (
        base.groupby("StudentCode", dropna=False)
        .agg(
            TotalMarks=("Score", "sum"),
            AverageScore=("Score", "mean"),
            LastActivity=("Date", "max"),
            Level=("Level", lambda s: s.mode().iat[0] if not s.mode().empty else (s.iloc[0] if len(s) else None)),
            Student=("Name", lambda s: s.mode().iat[0] if not s.mode().empty else (s.iloc[0] if len(s) else "")),
        )
        .reset_index()
        .merge(completed, on="StudentCode", how="left")
    )

    if agg.empty:
        return pd.DataFrame(columns=column_order)

    agg["AssignmentsCompleted"] = agg["AssignmentsCompleted"].fillna(0).astype(int)

    if min_assignments is not None:
        agg = agg[agg["AssignmentsCompleted"] >= int(min_assignments)]

    if agg.empty:
        return pd.DataFrame(columns=column_order)

    agg["AverageScore"] = agg["AverageScore"].round(2)
    agg = agg.sort_values(["TotalMarks", "LastActivity"], ascending=[False, False]).reset_index(drop=True)
    agg.insert(0, "Rank", agg.index + 1)
    agg = agg[column_order]
    return agg

