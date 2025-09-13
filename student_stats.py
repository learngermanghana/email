import pandas as pd
from typing import Optional

try:
    import firebase_admin
    from firebase_admin import firestore
except ModuleNotFoundError:  # fallback if firebase is not installed
    firebase_admin = None
    firestore = None


def _load_assignments_from_firestore(collection: str) -> pd.DataFrame:
    """Load assignment results from a Firestore collection.

    The Firestore documents are expected to contain ``studentcode``, ``assignment``
    and ``score`` fields. An optional ``level`` field may be present; if not,
    it will be obtained from ``students.csv`` during merging.
    """
    if firebase_admin is None:
        raise ImportError("firebase_admin is required for Firestore operations")

    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    db = firestore.client()
    docs = db.collection(collection).stream()
    data = [doc.to_dict() for doc in docs]
    return pd.DataFrame(data)


def load_and_rank_students(
    students_csv: str,
    assignments_csv: Optional[str] = None,
    firestore_collection: Optional[str] = None,
    *,
    min_assignments: int = 3,
) -> pd.DataFrame:
    """Load student and assignment data and produce ranked results.

    Exactly one of ``assignments_csv`` or ``firestore_collection`` must be
    provided.

    Students with fewer than ``min_assignments`` completed assignments are
    excluded from the results.

    Parameters
    ----------
    students_csv:
        Path to the ``students.csv`` file.
    assignments_csv:
        Optional path to a CSV with columns ``studentcode``, ``assignment``,
        ``score`` and optionally ``level``.
    firestore_collection:
        Name of a Firestore collection containing assignment documents.
    min_assignments:
        Minimum number of assignments a student must have completed to appear
        on the leaderboard.

    Returns
    -------
    ``pandas.DataFrame`` with columns ``StudentCode``, ``Level``,
    ``assignments_count``, ``total_score`` and ``rank``.
    """

    if bool(assignments_csv) == bool(firestore_collection):
        raise ValueError("Specify exactly one of assignments_csv or firestore_collection")

    students_df = pd.read_csv(students_csv)
    student_levels = students_df[["StudentCode", "Level", "Name"]]

    if assignments_csv:
        assignments_df = pd.read_csv(assignments_csv)
    else:
        assignments_df = _load_assignments_from_firestore(firestore_collection)

    merged = assignments_df.merge(
        student_levels,
        left_on=["studentcode", "level"],
        right_on=["StudentCode", "Level"],
        how="inner",
    )

    summary = (
        merged.groupby(["StudentCode", "Name", "Level"])
        .agg(assignments_count=("assignment", "count"), total_score=("score", "sum"))
        .reset_index()
    )

    summary = summary[summary["assignments_count"] >= min_assignments]

    summary["rank"] = summary.groupby("Level")["total_score"].rank(
        ascending=False, method="dense"
    )

    return summary.sort_values(["Level", "rank", "StudentCode"]).reset_index(drop=True)
