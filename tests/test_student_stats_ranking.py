import pandas as pd
from pathlib import Path

from student_stats import load_and_rank_students


def _write_csv(path: Path, data: str) -> None:
    path.write_text(data)


def test_exclusion_and_ranking(tmp_path: Path) -> None:
    students_data = (
        "Name,Level,StudentCode\n"
        "Alice,A1,a1\n"
        "Bob,A1,b1\n"
        "Cara,A1,c1\n"
        "Dan,A2,d1\n"
        "Eve,A2,e1\n"
    )
    assignments_data = (
        "studentcode,assignment,score,level\n"
        "a1,hw1,80,A1\n"
        "a1,hw2,70,A1\n"
        "a1,hw3,90,A1\n"
        "b1,hw1,100,A1\n"
        "b1,hw2,100,A1\n"
        "c1,hw1,10,A1\n"
        "c1,hw2,20,A1\n"
        "c1,hw3,10,A1\n"
        "c1,hw4,30,A1\n"
        "d1,hw1,50,A2\n"
        "d1,hw2,60,A2\n"
        "d1,hw3,70,A2\n"
        "e1,hw1,90,A2\n"
        "e1,hw2,80,A2\n"
        "e1,hw3,75,A2\n"
    )

    students_csv = tmp_path / "students.csv"
    assignments_csv = tmp_path / "assignments.csv"
    _write_csv(students_csv, students_data)
    _write_csv(assignments_csv, assignments_data)

    result = load_and_rank_students(
        students_csv=students_csv,
        assignments_csv=assignments_csv,
    )

    # Students with fewer than 3 assignments should be excluded
    assert "b1" not in result["StudentCode"].values

    expected = pd.DataFrame(
        {
            "StudentCode": ["a1", "c1", "e1", "d1"],
            "Name": ["Alice", "Cara", "Eve", "Dan"],
            "Level": ["A1", "A1", "A2", "A2"],
            "assignments_count": [3, 4, 3, 3],
            "total_score": [240, 70, 245, 180],
            "rank": [1.0, 2.0, 1.0, 2.0],
        }
    )

    pd.testing.assert_frame_equal(result.reset_index(drop=True), expected)
