# leaderboard_logic.py
import pandas as pd

SECTION_POINTS = {"teil1": 5, "teil2": 10, "teil3": 10}

def compute_leaderboard(attempts_df: pd.DataFrame,
                        roster_df: pd.DataFrame,
                        class_name: str | None = None,
                        start: pd.Timestamp | None = None,
                        end: pd.Timestamp | None = None) -> pd.DataFrame:
    """
    attempts_df columns (expected):
      StudentCode, section (teil1|teil2|teil3), is_correct (0/1 or True/False), timestamp
    roster_df columns (expected):
      StudentCode, Name (or First/Last), ClassName
    """

    df = attempts_df.copy()

    # Normalize
    df["section"] = df["section"].str.lower().str.strip()
    if df["is_correct"].dtype != "bool":
        df["is_correct"] = df["is_correct"].astype(int).clip(0, 1).astype(bool)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # Filters
    if class_name:
        roster_codes = roster_df.loc[roster_df["ClassName"] == class_name, "StudentCode"]
        df = df[df["StudentCode"].isin(roster_codes)]
    if start is not None:
        df = df[df["timestamp"] >= start]
    if end is not None:
        df = df[df["timestamp"] < end]

    # Points per attempt (only if correct)
    df["max_points"] = df["section"].map(SECTION_POINTS).fillna(0)
    df["earned"] = df["max_points"].where(df["is_correct"], 0)

    # Aggregate per student
    agg = (
        df.groupby("StudentCode")
          .agg(total_points=("earned", "sum"),
               last_seen=("timestamp", "max"),
               attempts=("section", "count"))
          .reset_index()
    )

    # Join names/class & sort: points desc, recent first
    out = (agg.merge(roster_df[["StudentCode", "ClassName"] + 
                     [c for c in roster_df.columns if c.lower() in {"name","firstname","lastname"}]],
                     on="StudentCode", how="left")
             .sort_values(["total_points", "last_seen"], ascending=[False, False])
             .reset_index(drop=True))

    # Optional: top N
    return out
