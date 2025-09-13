import pandas as pd
import streamlit as st

from student_stats import load_and_rank_students

st.title("\U0001F3C6 Leaderboard")


@st.cache_data(show_spinner="Loading leaderboard...")
def load_leaderboard() -> pd.DataFrame:
    """Load ranked student results."""
    students_csv = st.secrets.get("students_csv", "students.csv")
    assignments_csv = st.secrets.get(
        "assignments_csv",
        "https://docs.google.com/spreadsheets/d/1BRb8p3Rq0VpFCLSwL4eS9tSgXBo9hSWzfW_J_7W36NQ/gviz/tq?tqx=out:csv&tq=select%20*&gid=2121051612",
    )
    firestore_collection = st.secrets.get("assignments_collection")
    try:
        return load_and_rank_students(
            students_csv=students_csv,
            assignments_csv=assignments_csv,
            firestore_collection=firestore_collection,
            min_assignments=3,
        )
    except Exception as exc:  # pragma: no cover - network / config errors
        st.error(f"Failed to load leaderboard: {exc}")
        return pd.DataFrame()


if st.button("Refresh leaderboard"):
    load_leaderboard.clear()
    st.rerun()

leaderboard_df = load_leaderboard()

if leaderboard_df.empty:
    st.info("No leaderboard data available.")
else:
    for level, group in leaderboard_df.groupby("Level"):
        st.subheader(f"Level {level}")
        display_df = group[
            ["rank", "Name", "StudentCode", "assignments_count", "total_score"]
        ].rename(
            columns={
                "rank": "Rank",
                "Name": "Name",
                "StudentCode": "Code",
                "assignments_count": "Assignments",
                "total_score": "Total Score",
            }
        )
        st.table(display_df.reset_index(drop=True))
