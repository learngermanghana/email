import pandas as pd
import tempfile
from pathlib import Path

from student_stats import load_and_rank_students


def _write_csv(path: Path, data: str) -> None:
    path.write_text(data)


def test_load_and_rank_students(tmp_path: Path) -> None:
    students_data = (
        "Name,Level,StudentCode\n"
        "Alice,A1,a1\n"
        "Bob,A1,b1\n"
        "Cara,A2,c1\n"
    )
    assignments_data = (
        "studentcode,assignment,score,level\n"
        "a1,hw1,80,A1\n"
        "a1,hw2,90,A1\n"
        "a1,hw3,70,A1\n"
        "b1,hw1,50,A1\n"
        "b1,hw2,60,A1\n"
        "c1,hw1,85,A2\n"
        "c1,hw2,95,A2\n"
        "c1,hw3,90,A2\n"
        "c1,hw4,100,A2\n"
    )

    students_csv = tmp_path / "students.csv"
    assignments_csv = tmp_path / "assignments.csv"
    _write_csv(students_csv, students_data)
    _write_csv(assignments_csv, assignments_data)

    result = load_and_rank_students(
        students_csv=students_csv,
        assignments_csv=assignments_csv,
    )

    expected = pd.DataFrame(
        {
            "StudentCode": ["a1", "c1"],
            "Name": ["Alice", "Cara"],
            "Level": ["A1", "A2"],
            "assignments_count": [3, 4],
            "total_score": [240, 370],
            "rank": [1.0, 1.0],
        }
    )

    pd.testing.assert_frame_equal(result.reset_index(drop=True), expected)
