import pandas as pd
from typing import Optional, Tuple, Union

from config import ASSIGNMENT_LINKS

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
    return_assignments: bool = False,
) -> Union[pd.DataFrame, Tuple[pd.DataFrame, pd.DataFrame]]:
    """Load student and assignment data and produce ranked results.

    Exactly one of ``assignments_csv`` or ``firestore_collection`` must be
    provided.

    Parameters
    ----------
    students_csv:
        Path to the ``students.csv`` file.
    assignments_csv:
        Optional path to a CSV with columns ``studentcode``, ``assignment``,
        ``score`` and optionally ``level``.
    firestore_collection:
        Name of a Firestore collection containing assignment documents.

    Returns
    -------
    ``pandas.DataFrame`` with columns ``StudentCode``, ``Level``,
    ``assignment_count``, ``total_score`` and ``rank``.

    If ``return_assignments`` is ``True`` an additional DataFrame containing
    per-assignment records (including an ``assignment_link`` column) is
    returned as a second element of the tuple.
    """

    if bool(assignments_csv) == bool(firestore_collection):
        raise ValueError("Specify exactly one of assignments_csv or firestore_collection")

    students_df = pd.read_csv(students_csv)
    student_levels = students_df[["StudentCode", "Level", "Name"]]

    if assignments_csv:
        assignments_df = pd.read_csv(assignments_csv)
    else:
        assignments_df = _load_assignments_from_firestore(firestore_collection)

    assignments_df["assignment_link"] = assignments_df["assignment"].map(
        ASSIGNMENT_LINKS
    )

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

    summary = summary[summary["assignments_count"] >= 3]

    summary["rank"] = summary.groupby("Level")["total_score"].rank(
        ascending=False, method="dense"
    )

    summary = summary.sort_values(["Level", "rank", "StudentCode"]).reset_index(
        drop=True
    )

    if return_assignments:
        return summary, merged
    return summary
