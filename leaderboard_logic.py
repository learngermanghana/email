# pages/02_Leaderboards.py
# Live Tutor Leaderboards (All Levels + per-level) from a Google Sheet
# Expected columns (case-insensitive):
#   studentcode, name, assignment, score, comments, date, level, link

from __future__ import annotations

import io
import re
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import quote_plus

import pandas as pd
import requests
import streamlit as st

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG: set your sheet here
# ──────────────────────────────────────────────────────────────────────────────
SHEET_ID = "1BRb8p3Rq0VpFCLSwL4eS9tSgXBo9hSWzfW_J_7W36NQ"  # <— replace if needed
SHEET_NAME = "Sheet1"                                     # <— replace if needed

# Qualifying rule: min distinct assignments after dedupe
DEFAULT_MIN_ASSIGNMENTS = 3

# ──────────────────────────────────────────────────────────────────────────────
# Streamlit page setup
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Leaderboards", page_icon="🏆", layout="wide")
st.title("🏆 Tutor Leaderboards")

# Versioning for manual refresh
if "lb_ver" not in st.session_state:
    st.session_state["lb_ver"] = 0

# Top controls
top_c1, top_c2, top_c3 = st.columns([1.0, 1.0, 0.6])
with top_c1:
    min_assignments = st.number_input(
        "Minimum assignments to qualify",
        min_value=1, max_value=10, value=DEFAULT_MIN_ASSIGNMENTS, step=1
    )
with top_c2:
    top_n = st.number_input("Top N", min_value=5, max_value=500, value=50, step=5)
with top_c3:
    def _refresh():
        try:
            _load_sheet_cached.clear()
        except Exception:
            pass
        st.session_state["lb_ver"] += 1
        st.rerun()
    st.button("🔄 Refresh", use_container_width=True, on_click=_refresh)

# ──────────────────────────────────────────────────────────────────────────────
# Data loading (live from Google Sheet)
# ──────────────────────────────────────────────────────────────────────────────

def _sheet_csv_url(sheet_id: str, sheet_name: str) -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq"
        f"?tqx=out:csv&sheet={quote_plus(sheet_name)}"
    )

@st.cache_data(ttl=60)
def _load_sheet_cached(sheet_id: str, sheet_name: str) -> pd.DataFrame:
    url = _sheet_csv_url(sheet_id, sheet_name)
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        txt = r.text
        if "<html" in txt[:512].lower():
            raise ValueError(
                "Expected CSV but got HTML (check sheet sharing & sheet name)."
            )
        df = pd.read_csv(
            io.StringIO(txt),
            dtype=str,
            keep_default_na=True,
            na_values=["", " ", "nan", "NaN", "None"],
        )
    except Exception as e:
        logging.exception("Failed loading scores sheet")
        st.error(f"❌ Could not load the scores sheet. {e}")
        return pd.DataFrame()

    # Normalize header names -> canonical columns
    df.columns = df.columns.astype(str).str.strip()
    lower = {c.lower().strip(): c for c in df.columns}

    def pick(name: str) -> Optional[str]:
        return lower.get(name)

    # Map to canonical set
    rename_map = {}
    if pick("studentcode"): rename_map[lower["studentcode"]] = "StudentCode"
    if pick("name"):        rename_map[lower["name"]] = "Name"
    if pick("assignment"):  rename_map[lower["assignment"]] = "Assignment"
    if pick("score"):       rename_map[lower["score"]] = "Score"
    if pick("comments"):    rename_map[lower["comments"]] = "Comments"
    if pick("date"):        rename_map[lower["date"]] = "Date"
    if pick("level"):       rename_map[lower["level"]] = "Level"
    if pick("link"):        rename_map[lower["link"]] = "Link"

    df = df.rename(columns=rename_map)

    # Ensure all expected columns exist
    for col in ["StudentCode", "Name", "Assignment", "Score", "Date", "Level"]:
        if col not in df.columns:
            df[col] = pd.NA

    # Trim/normalize values
    df["StudentCode"] = df["StudentCode"].astype(str).str.strip().str.lower()
    df["Name"] = df["Name"].astype(str).str.strip()
    df["Assignment"] = df["Assignment"].astype(str).str.strip()
    df["Level"] = df["Level"].astype(str).str.upper().str.strip()
    df["Score"] = pd.to_numeric(df["Score"], errors="coerce").fillna(0.0)

    # Robust date parsing
    def _parse_date(s):
        if pd.isna(s) or str(s).strip() == "":
            return pd.NaT
        x = str(s).strip()
        for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%y", "%d/%m/%y"):
            try:
                return pd.to_datetime(x, format=fmt, errors="raise")
            except Exception:
                pass
        # Fallback: let pandas try
        return pd.to_datetime(x, errors="coerce")

    df["Date"] = df["Date"].apply(_parse_date)

    # Keep only rows that have a student and an assignment
    df = df[(df["StudentCode"].notna()) & (df["StudentCode"] != "") &
            (df["Assignment"].notna()) & (df["Assignment"] != "")]
    return df

scores_raw = _load_sheet_cached(SHEET_ID, SHEET_NAME)
if scores_raw.empty:
    st.warning("No data available from the sheet.")
    st.stop()

# ──────────────────────────────────────────────────────────────────────────────
# Leaderboard logic
# ──────────────────────────────────────────────────────────────────────────────

SECTION_POINTS = {"teil1": 5, "teil2": 10, "teil3": 10}  # unused here, kept for parity

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
    Keep only the latest attempt per (StudentCode, AssignmentKey).
    If same date appears twice, keep the higher score.
    """
    tmp = scores_df.copy()
    tmp["_AssignmentKey"] = tmp["Assignment"].apply(_canon_assignment)

    # Order so that the last row per group is kept:
    #   1) by Date ascending (latest is last)
    #   2) by Score ascending (higher last if same date)
    tmp = tmp.sort_values(["Date", "Score"], ascending=[True, True])

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

def compute_leaderboard(scores_df: pd.DataFrame, *, level: str | None, min_assignments: int) -> pd.DataFrame:
    df = scores_df.copy()

    if level:
        df = df[df["Level"] == level.upper()]

    # Deduplicate multiple attempts of same assignment
    kept = _dedupe_latest_attempt(df)

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
            Student=("Name",  lambda s: s.mode().iat[0] if not s.mode().empty else (s.iloc[0] if len(s) else "")),
        )
        .reset_index()
        .merge(completed, on="StudentCode", how="left")
    )

    # Apply qualifying rule
    agg = agg[agg["AssignmentsCompleted"].fillna(0) >= int(min_assignments)]

    if agg.empty:
        return pd.DataFrame(columns=[
            "Rank", "Student", "StudentCode", "Level",
            "TotalMarks", "AssignmentsCompleted", "AverageScore", "LastActivity"
        ])

    agg["AverageScore"] = agg["AverageScore"].round(2)
    agg = agg.sort_values(["TotalMarks", "LastActivity"], ascending=[False, False]).reset_index(drop=True)
    agg.insert(0, "Rank", agg.index + 1)
    agg = agg[[
        "Rank", "Student", "StudentCode", "Level",
        "TotalMarks", "AssignmentsCompleted", "AverageScore", "LastActivity",
    ]]
    return agg

# ──────────────────────────────────────────────────────────────────────────────
# Build UI
# ──────────────────────────────────────────────────────────────────────────────

# Show the automatic date span used (min -> max in the sheet)
min_dt = scores_raw["Date"].min(skipna=True)
max_dt = scores_raw["Date"].max(skipna=True)
if pd.notna(min_dt) and pd.notna(max_dt):
    st.caption(f"Live data from sheet • Date span: **{min_dt.date()} → {max_dt.date()}**")
else:
    st.caption("Live data from sheet • Some rows have no date")

# Detect levels present
levels = compute_level_list(scores_raw)

tabs = st.tabs(["All Levels"] + levels)

# All Levels
with tabs[0]:
    st.subheader("All Levels (qualified only)")
    lb_all = compute_leaderboard(scores_raw, level=None, min_assignments=min_assignments)
    if lb_all.empty:
        st.info("No students meet the qualifying rule yet.")
    else:
        st.dataframe(lb_all.head(int(top_n)), use_container_width=True)
        csv = lb_all.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download CSV (All Levels)",
            data=csv,
            file_name="leaderboard_all_levels.csv",
            mime="text/csv",
        )

# Per-level tabs
for i, lvl in enumerate(levels, start=1):
    with tabs[i]:
        st.subheader(f"Level {lvl} (qualified only)")
        lb = compute_leaderboard(scores_raw, level=lvl, min_assignments=min_assignments)
        if lb.empty:
            st.info(f"No students meet the qualifying rule for {lvl}.")
        else:
            st.dataframe(lb.head(int(top_n)), use_container_width=True)
            csv = lb.to_csv(index=False).encode("utf-8")
            st.download_button(
                f"⬇️ Download CSV (Level {lvl})",
                data=csv,
                file_name=f"leaderboard_{lvl}.csv",
                mime="text/csv",
            )
