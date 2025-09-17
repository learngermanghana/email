# leaderboard_logic.py
from __future__ import annotations
import pandas as pd

def compute_level_list(df: pd.DataFrame) -> list[str]:
    levels = sorted(x for x in df["Level"].dropna().unique())
    return levels or ["A1", "A2"]

def compute_leaderboard(
    scores_df: pd.DataFrame,
    *,
    level: str | None = None,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
    search: str | None = None,
) -> pd.DataFrame:
    """Aggregate:
      - TotalMarks = sum(Score)
      - AssignmentsCompleted = count DISTINCT Assignment with a non-null (or >=0) Score
      - LastActivity = latest Date
    """
    df = scores_df.copy()

    # Filters
    if level:
        df = df[df["Level"] == level.upper()]
    if start is not None:
        df = df[df["Date"] >= start]
    if end is not None:
        df = df[df["Date"] < end]
    if search:
        needle = str(search).strip().lower()
        df = df[
            df["StudentCode"].str.contains(needle, case=False, na=False) |
            df["Name"].str.lower().str.contains(needle, na=False)
        ]

    if df.empty:
        return pd.DataFrame(columns=[
            "Rank", "Student", "StudentCode", "Level",
            "TotalMarks", "AssignmentsCompleted", "AverageScore", "LastActivity"
        ])

    # Count DISTINCT assignment names per student (completed = has a row)
    # Use nunique on Assignment; if you want only assignments with score>0, filter first.
    completed = (
        df.groupby(["StudentCode"], dropna=False)["Assignment"]
          .nunique()
          .rename("AssignmentsCompleted")
    )

    agg = (
        df.groupby(["StudentCode"], dropna=False)
          .agg(
              TotalMarks=("Score", "sum"),
              AverageScore=("Score", "mean"),
              LastActivity=("Date", "max"),
              Level=("Level", lambda s: s.mode().iat[0] if not s.mode().empty else (s.iloc[0] if len(s) else None)),
              Student=("Name",  lambda s: s.mode().iat[0] if not s.mode().empty else (s.iloc[0] if len(s) else "")),
          )
          .reset_index()
          .merge(completed, on="StudentCode", how="left")
    )

    # Order & tidy
    agg["AverageScore"] = agg["AverageScore"].round(2)
    agg = agg.sort_values(["TotalMarks", "LastActivity"], ascending=[False, False]).reset_index(drop=True)
    agg.insert(0, "Rank", agg.index + 1)
    agg = agg[[
        "Rank", "Student", "StudentCode", "Level",
        "TotalMarks", "AssignmentsCompleted", "AverageScore", "LastActivity"
    ]]
    return agg
