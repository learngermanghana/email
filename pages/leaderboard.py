import pandas as pd
import streamlit as st

from student_stats import load_and_rank_students

st.title("\U0001F3C6 Leaderboard")


@st.cache_data(show_spinner="Loading leaderboard...")
def load_leaderboard() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load ranked student results and per-assignment details."""
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
            return_assignments=True,
        )
    except Exception as exc:  # pragma: no cover - network / config errors
        st.error(f"Failed to load leaderboard: {exc}")
        return pd.DataFrame(), pd.DataFrame()


if st.button("Refresh leaderboard"):
    load_leaderboard.clear()
    st.experimental_rerun()

leaderboard_df, assignments_df = load_leaderboard()

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

    if not assignments_df.empty:
        st.subheader("Assignments")
        display_assignments = assignments_df[
            ["Name", "assignment", "score", "assignment_link"]
        ].copy()
        display_assignments["assignment"] = display_assignments.apply(
            lambda r: f"[{r['assignment']}]({r['assignment_link']})"
            if pd.notnull(r["assignment_link"])
            else r["assignment"],
            axis=1,
        )
        st.markdown(
            display_assignments[["Name", "assignment", "score"]]
            .rename(columns={"assignment": "Assignment", "score": "Score"})
            .to_html(escape=False, index=False),
            unsafe_allow_html=True,
        )
