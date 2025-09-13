from pathlib import Path

import pandas as pd

from student_stats import load_and_rank_students
from config import ASSIGNMENT_LINKS


def _write_csv(path: Path, data: str) -> None:
    path.write_text(data)


def test_assignment_links_join(tmp_path: Path) -> None:
    students_data = (
        "Name,Level,StudentCode\n"
        "Alice,A1,a1\n"
    )
    assignments_data = (
        "studentcode,assignment,score,level\n"
        "a1,hw1,80,A1\n"
        "a1,unknown,70,A1\n"
    )
    students_csv = tmp_path / "students.csv"
    assignments_csv = tmp_path / "assignments.csv"
    _write_csv(students_csv, students_data)
    _write_csv(assignments_csv, assignments_data)

    summary, assignments = load_and_rank_students(
        students_csv=students_csv,
        assignments_csv=assignments_csv,
        return_assignments=True,
    )

    assert "assignment_link" in assignments.columns

    hw1_link = assignments.loc[assignments["assignment"] == "hw1", "assignment_link"].iloc[0]
    assert hw1_link == ASSIGNMENT_LINKS["hw1"]

    unknown_link = assignments.loc[
        assignments["assignment"] == "unknown", "assignment_link"
    ].iloc[0]
    assert pd.isna(unknown_link)

