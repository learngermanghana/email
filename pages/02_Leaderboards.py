# pages/02_Leaderboards.py
from __future__ import annotations

from datetime import datetime, timedelta
import os, sys
import pandas as pd
import streamlit as st

# --- Make imports work when this file lives in /email/pages ---
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # -> /email
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Imports from our modules
from scores_loading import load_scores, clear_scores_cache
from leaderboard_logic import compute_leaderboard, compute_level_list

st.set_page_config(page_title="Leaderboards", page_icon="🏆", layout="wide")
st.title("🏆 Tutor Leaderboards")

# Version for cache-busting
if "ver" not in st.session_state:
    st.session_state["ver"] = 0

def refresh_all():
    clear_scores_cache()
    st.session_state["ver"] += 1
    st.rerun()

# Filters
with st.container():
    col1, col2, col3, col4 = st.columns([1.3, 1.3, 1.4, 0.8])
    with col1:
        start_date = st.date_input("From", value=(datetime.utcnow() - timedelta(days=30)).date())
    with col2:
        end_date = st.date_input("To", value=datetime.utcnow().date())
    with col3:
        search_q = st.text_input("Search (name or code)")
    with col4:
        st.button("🔄 Refresh", use_container_width=True, on_click=refresh_all)

# Load scores BEFORE building tabs
scores = load_scores(version=st.session_state["ver"])
if scores is None or scores.empty:
    st.warning("No data found. Check sheet sharing and tab name (default tries: Scores/Sheet1).")
    st.stop()

# Build level tabs (All + per level)
levels = compute_level_list(scores)
tabs = st.tabs(["All Levels"] + levels)

# Convert date filters
start_ts = pd.to_datetime(datetime.combine(start_date, datetime.min.time())) if start_date else None
end_ts = pd.to_datetime(datetime.combine(end_date, datetime.min.time())) + pd.Timedelta(days=1) if end_date else None

# All Levels
with tabs[0]:
    st.subheader("All Levels")
    lb = compute_leaderboard(scores_df=scores, level=None, start=start_ts, end=end_ts, search=search_q)
    st.dataframe(lb, use_container_width=True)
    st.download_button(
        "⬇️ Download CSV (All Levels)",
        data=lb.to_csv(index=False).encode("utf-8"),
        file_name="leaderboard_all_levels.csv",
        mime="text/csv",
    )

# Per-level tabs
for i, lvl in enumerate(levels, start=1):
    with tabs[i]:
        st.subheader(f"Level {lvl}")
        lb = compute_leaderboard(scores_df=scores, level=lvl, start=start_ts, end=end_ts, search=search_q)
        st.dataframe(lb, use_container_width=True)
        st.download_button(
            f"⬇️ Download CSV (Level {lvl})",
            data=lb.to_csv(index=False).encode("utf-8"),
            file_name=f"leaderboard_{lvl}.csv",
            mime="text/csv",
        )
