# pages/02_Leaderboards.py
# Streamlit page: Tutor view of leaderboards by level (A1, A2, ...)
# - Shows an "All Levels" view and auto-creates a tab per detected level
# - Filters by date range and class, quick search, CSV export
# - Works with your existing data loaders

from __future__ import annotations

import io
import re
from datetime import datetime, timedelta
from typing import Iterable, Optional

import pandas as pd
import streamlit as st

# ---- Imports from your project ------------------------------------------------
# Adjust these imports to match your project structure if needed
try:
    from data_loading import load_student_data, _load_student_data_cached  # roster
except Exception:
    # Fallback path if your module lives under src/
    from src.data_loading import load_student_data, _load_student_data_cached  # type: ignore

# Attempts loader must return a DataFrame with columns at least:
#   StudentCode, section (teil1|teil2|teil3), is_correct (bool/int), timestamp, [optional] level
try:
    from attempts_loading import load_attempts, _load_attempts_cached  # your function
except Exception:
    # If your code names differ, change the import above and remove this stub.
    def load_attempts(*, version: int | None = None) -> pd.DataFrame:  # type: ignore
        raise RuntimeError(
            "Missing attempts loader. Import your attempts loader as `load_attempts` "
            "that returns a DataFrame with StudentCode, section, is_correct, timestamp, [level]."
        )
    class _Dummy:
        def clear(self):
            pass
    _load_attempts_cached = _Dummy()

# ---- Scoring ------------------------------------------------------------------
SECTION_POINTS = {"teil1": 5, "teil2": 10, "teil3": 10}

# ---- Helpers ------------------------------------------------------------------

def _infer_level_from_string(s: str | None) -> Optional[str]:
    if not s:
        return None
    m = re.search(r"\b(A1|A2|B1|B2|C1|C2)\b", str(s).upper())
    return m.group(1) if m else None


def _derive_roster_level_column(roster_df: pd.DataFrame) -> pd.Series:
    cols = {c.lower(): c for c in roster_df.columns}
    if "level" in cols:
        return roster_df[cols["level"]].astype(str).str.upper()
    # Try from ClassName
    source = None
    for key in ("classname", "class_name", "class", "group", "course"):
        if key in cols:
            source = roster_df[cols[key]]
            break
    if source is None:
        return pd.Series([None] * len(roster_df), index=roster_df.index, dtype="object")
    return source.apply(_infer_level_from_string)


def _compose_name(row: pd.Series) -> str:
    # Tries common name columns; adjust if your roster uses a different schema
    lc = {c.lower(): c for c in row.index}
    if "name" in lc:
        return str(row[lc["name"]]).strip()
    first = row.get(lc.get("firstname", ""), "") if lc.get("firstname") else ""
    last = row.get(lc.get("lastname", ""), "") if lc.get("lastname") else ""
    full = (str(first) + " " + str(last)).strip()
    return full or row.get("StudentCode", "")


def normalize_attempts(df: pd.DataFrame, roster_df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    # Normalize columns
    out.columns = out.columns.astype(str)
    out.columns = out.columns.str.strip()
    out.rename(columns={c: "StudentCode" for c in out.columns if c.lower() == "studentcode"}, inplace=True)
    # section
    if "section" in out.columns:
        out["section"] = out["section"].astype(str).str.lower().str.strip()
    else:
        out["section"] = None
    # is_correct
    if "is_correct" in out.columns:
        if out["is_correct"].dtype != bool:
            out["is_correct"] = out["is_correct"].astype(str).str.lower().map({
                "true": True, "1": True, "yes": True, "y": True,
                "false": False, "0": False, "no": False, "n": False,
            }).fillna(False)
    else:
        # If no is_correct, treat any attempt as 0 points unless explicit `points`
        out["is_correct"] = False
    # timestamp
    if "timestamp" in out.columns:
        out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    else:
        out["timestamp"] = pd.Timestamp.utcnow()
    # level: prefer attempts.level, else roster-derived
    if "level" in out.columns:
        out["level"] = out["level"].astype(str).str.upper()
    else:
        # Join inferred roster level by StudentCode
        ro = roster_df[["StudentCode", "_Level"]].drop_duplicates()
        out = out.merge(ro, on="StudentCode", how="left")
        out.rename(columns={"_Level": "level"}, inplace=True)
    # if points column exists, use it; else compute from section + is_correct
    if "points" in out.columns:
        out["points"] = pd.to_numeric(out["points"], errors="coerce").fillna(0).astype(int)
    else:
        out["points"] = out["section"].map(SECTION_POINTS).fillna(0).astype(int)
        out.loc[~out["is_correct"], "points"] = 0
    return out


def compute_leaderboard(
    attempts_df: pd.DataFrame,
    roster_df: pd.DataFrame,
    *,
    level: str | None = None,
    class_name: str | None = None,
    start: Optional[pd.Timestamp] = None,
    end: Optional[pd.Timestamp] = None,
    search: str | None = None,
) -> pd.DataFrame:
    df = attempts_df.copy()

    # Filters
    if level:
        df = df[df["level"] == level.upper()]
    if start is not None:
        df = df[df["timestamp"] >= start]
    if end is not None:
        df = df[df["timestamp"] < end]

    # Join roster for names & classes
    cols = [c for c in ("StudentCode", "ClassName", "_Name", "_Level") if c in roster_df.columns]
    joined = df.merge(roster_df[cols], on="StudentCode", how="left")

    if class_name:
        joined = joined[joined["ClassName"].astype(str) == class_name]

    if joined.empty:
        return pd.DataFrame(columns=[
            "Rank", "Student", "StudentCode", "Level", "ClassName", "TotalPoints",
            "Attempts", "Accuracy", "LastActivity",
        ])

    # Aggregate per student
    agg = (
        joined.groupby(["StudentCode"], dropna=False)
        .agg(
            TotalPoints=("points", "sum"),
            Attempts=("points", "count"),
            Correct=("is_correct", "sum"),
            LastActivity=("timestamp", "max"),
            Level=("_Level", "max"),  # roster-derived level
            ClassName=("ClassName", lambda s: s.mode().iat[0] if not s.mode().empty else s.iloc[0]),
            Student=("_Name", "max"),
        )
        .reset_index()
    )

    # Accuracy
    agg["Accuracy"] = (agg["Correct"].astype(float) / agg["Attempts"].clip(lower=1) * 100).round(1)

    # Sorting: TotalPoints desc, then LastActivity desc
    agg = agg.sort_values(["TotalPoints", "LastActivity"], ascending=[False, False]).reset_index(drop=True)
    agg.insert(0, "Rank", agg.index + 1)

    # Final tidy columns
    agg = agg[[
        "Rank", "Student", "StudentCode", "Level", "ClassName",
        "TotalPoints", "Attempts", "Accuracy", "LastActivity",
    ]]
    return agg


# ---- UI ----------------------------------------------------------------------
st.set_page_config(page_title="Leaderboards", page_icon="🏆", layout="wide")

st.title("🏆 Tutor Leaderboards")

# Versioning for cache-busting
if "ver" not in st.session_state:
    st.session_state["ver"] = 0

# Filters row
with st.container():
    col1, col2, col3, col4, col5 = st.columns([1.3, 1.3, 1.0, 1.0, 0.8])
    with col1:
        start_date = st.date_input("From", value=(datetime.utcnow() - timedelta(days=30)).date())
    with col2:
        end_date = st.date_input("To", value=datetime.utcnow().date())
    with col3:
        search_q = st.text_input("Search (name or code)")
    with col4:
        top_n = st.number_input("Top N", min_value=5, max_value=200, value=50, step=5)
    with col5:
        def _refresh_all():
            try: _load_student_data_cached.clear()
            except Exception: pass
            try: _load_attempts_cached.clear()
            except Exception: pass
            st.session_state["ver"] += 1
            st.rerun()
        st.button("🔄 Refresh", use_container_width=True, on_click=_refresh_all)

# Load data BEFORE building tabs
roster = load_student_data(force_refresh=False, version=st.session_state["ver"])  # type: ignore[arg-type]
if roster is None or roster.empty:
    st.warning("Roster is empty or unavailable.")
    st.stop()

# Prepare roster features used by the UI
roster = roster.copy()
roster["_Level"] = _derive_roster_level_column(roster)
roster["_Name"] = roster.apply(_compose_name, axis=1)

# Available classes (dropna + sort)
classes = sorted(x for x in roster.get("ClassName", pd.Series(dtype=str)).dropna().unique())
classes_opts = ["All classes"] + classes

# Load attempts
attempts = load_attempts(version=st.session_state["ver"])  # type: ignore[arg-type]
attempts = normalize_attempts(attempts, roster)

# Detect levels (prefer attempts.level, else roster _Level)
levels = (
    pd.Series(sorted(set(x for x in attempts["level"].dropna().unique())))
    if "level" in attempts.columns and attempts["level"].notna().any()
    else pd.Series(sorted(x for x in roster["_Level"].dropna().unique()))
)
levels = levels.tolist() if len(levels) else ["A1", "A2"]  # sensible default

# Build tabs: All Levels + one per level
tabs = st.tabs(["All Levels"] + levels)

# Common filter dates to timestamps
start_ts = pd.to_datetime(datetime.combine(start_date, datetime.min.time())) if start_date else None
end_ts = pd.to_datetime(datetime.combine(end_date, datetime.min.time())) + pd.Timedelta(days=1) if end_date else None

# --- All Levels tab -----------------------------------------------------------
with tabs[0]:
    st.subheader("All Levels")

    cls = st.selectbox("Class filter", classes_opts, key="lb_all_class")
    class_filter = None if cls == "All classes" else cls

    lb = compute_leaderboard(
        attempts_df=attempts,
        roster_df=roster,
        level=None,
        class_name=class_filter,
        start=start_ts,
        end=end_ts,
        search=search_q,
    )
    if search_q:
        mask = (
            lb["Student"].astype(str).str.contains(search_q, case=False, na=False) |
            lb["StudentCode"].astype(str).str.contains(search_q, case=False, na=False)
        )
        lb = lb[mask]

    if lb.empty:
        st.info("No attempts in selected range.")
    else:
        st.dataframe(lb.head(int(top_n)), use_container_width=True)
        csv = lb.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download CSV (All Levels)", data=csv, file_name="leaderboard_all_levels.csv", mime="text/csv")

# --- Per-level tabs ------------------------------------------------------------
for i, lvl in enumerate(levels, start=1):
    with tabs[i]:
        st.subheader(f"Level {lvl}")

        # Classes available for this level
        lvl_classes = sorted(
            roster.loc[roster["_Level"] == lvl, "ClassName"].dropna().unique().tolist()
        )
        cls_opts = ["All classes"] + lvl_classes
        cls_sel = st.selectbox("Class filter", cls_opts, key=f"lb_class_{lvl}")
        class_filter = None if cls_sel == "All classes" else cls_sel

        lb = compute_leaderboard(
            attempts_df=attempts,
            roster_df=roster,
            level=lvl,
            class_name=class_filter,
            start=start_ts,
            end=end_ts,
            search=search_q,
        )
        if search_q:
            mask = (
                lb["Student"].astype(str).str.contains(search_q, case=False, na=False) |
                lb["StudentCode"].astype(str).str.contains(search_q, case=False, na=False)
            )
            lb = lb[mask]

        if lb.empty:
            st.info(f"No attempts for {lvl} in selected range.")
        else:
            st.dataframe(lb.head(int(top_n)), use_container_width=True)
            csv = lb.to_csv(index=False).encode("utf-8")
            st.download_button(
                f"⬇️ Download CSV (Level {lvl})",
                data=csv,
                file_name=f"leaderboard_{lvl}.csv",
                mime="text/csv",
            )

# End of file
