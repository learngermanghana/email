# leaderboard_logic.py
from __future__ import annotations
import re
import pandas as pd

def compute_level_list(df: pd.DataFrame) -> list[str]:
    levels = sorted(x for x in df["Level"].dropna().unique())
    return levels or ["A1", "A2"]

# --- Helpers ------------------------------------------------------------------

def _canon(s: str | None) -> str:
    """
    Canonicalize assignment names so duplicates match:
    - lowercase, strip extra spaces
    - normalize dashes
    - strip leading level tag like "A1 " / "B1 " etc.
    - collapse double spaces
    """
    if not isinstance(s, str):
        return ""
    x = s.strip().lower()
    x = x.replace("–", "-").replace("—", "-").replace("-", "-")
    x = re.sub(r"\s+", " ", x)
    # remove a leading level token (a1|a2|b1|b2|c1|c2) if present
    x = re.sub(r"^(a1|a2|b1|b2|c1|c2)\s+", "", x)
    return x

def _dedupe_latest(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep only the latest attempt per (StudentCode, AssignmentKey).
    On same date, keep the row with the higher Score.
    """
    tmp = df.copy()
    tmp["_AssignmentKey"] = tmp["Assignment"].apply(_canon)
    # Order so that the last row per group is the one we keep
    tmp = tmp.sort_values(["Date", "Score"], ascending=[True, True])
    keep_idx = tmp.groupby(["StudentCode", "_AssignmentKey"], dropna=False).tail(1).index
    return tmp.loc[keep_idx].drop(columns=["_AssignmentKey"])

# --- Main ---------------------------------------------------------------------

def compute_leaderboard(
    scores_df: pd.DataFrame,
    *,
    level: str | None = None,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
    search: str | None = None,
    min_assignments: int = 3,       # <-- NEW: threshold
) -> pd.DataFrame:
    """
    Aggregates per student after de-duplicating re-takes:
      - TotalMarks = sum(Score) over latest attempts
      - AssignmentsCompleted = distinct assignment count (after dedupe)
      - AverageScore = mean of kept attempts
      - LastActivity = latest Date
    Only students with AssignmentsCompleted >= min_assignments are ranked.
    """
    df = scores_df.copy()

    # Basic normalization (in case caller didn't)
    for col in ("StudentCode", "Name", "Assignment", "Level"):
        if col not in df.columns:
            df[col] = pd.NA
    df["StudentCode"] = df["StudentCode"].astype(str).str.strip().str.lower()
    df["Name"] = df["Name"].astype(str).str.strip()
    df["Assignment"] = df["Assignment"].astype(str).str.strip()
    df["Level"] = df["Level"].astype(str).str.upper().str.strip()
    df["Score"] = pd.to_numeric(df.get("Score", 0), errors="coerce").fillna(0.0)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    else:
        df["Date"] = pd.NaT

    # Filters first (so totals reflect the selected window)
    if level:
        df = df[df["Level"] == level.upper()]
    if start is not None:
        df = df[df["Date"].isna() | (df["Date"] >= start)]
    if end is not None:
        df = df[df["Date"].isna() | (df["Date"] < end)]

    # Drop rows without a student or an assignment
    df = df[(df["StudentCode"] != "") & (df["Assignment"] != "")]
    if df.empty:
        return pd.DataFrame(columns=[
            "Rank", "Student", "StudentCode", "Level",
            "TotalMarks", "AssignmentsCompleted", "AverageScore", "LastActivity"
        ])

    # Deduplicate: keep the latest attempt per student+assignment
    kept = _dedupe_latest(df)

    # Per-student aggregates
    agg_base = kept.copy()
    agg_base["_AssignmentKey"] = agg_base["Assignment"].apply(_canon)

    # Count distinct assignments completed
    completed = (
        agg_base.groupby("StudentCode")["_AssignmentKey"]
        .nunique()
        .rename("AssignmentsCompleted")
    )

    agg = (
        agg_base.groupby("StudentCode", dropna=False)
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

    # Apply minimum assignments rule
    agg = agg[agg["AssignmentsCompleted"].fillna(0) >= int(min_assignments)]

    # Optional search on the final table
    if search:
        q = str(search).strip().lower()
        mask = (
            agg["Student"].astype(str).str.lower().str.contains(q, na=False) |
            agg["StudentCode"].astype(str).str.contains(q, case=False, na=False)
        )
        agg = agg[mask]

    if agg.empty:
        return pd.DataFrame(columns=[
            "Rank", "Student", "StudentCode", "Level",
            "TotalMarks", "AssignmentsCompleted", "AverageScore", "LastActivity"
        ])

    # Finish
    agg["AverageScore"] = agg["AverageScore"].round(2)
    agg = agg.sort_values(["TotalMarks", "LastActivity"], ascending=[False, False]).reset_index(drop=True)
    agg.insert(0, "Rank", agg.index + 1)
    agg = agg[[
        "Rank", "Student", "StudentCode", "Level",
        "TotalMarks", "AssignmentsCompleted", "AverageScore", "LastActivity"
    ]]
    return agg
