from unittest.mock import patch
import pandas as pd
import importlib.util
import sys
from pathlib import Path
import os

# Ensure repository root is on sys.path for module dependencies
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_refresh_button_clears_caches():
    module_path = Path(__file__).resolve().parents[1] / "email.py"
    spec = importlib.util.spec_from_file_location("email_app", module_path)
    email_module = importlib.util.module_from_spec(spec)

    initial_df = pd.DataFrame({
        "studentcode": ["s0"],
        "level": ["A0"],
        "name": ["n0"],
        "phone": ["p0"],
        "paid": ["0"],
        "balance": ["0"],
        "contractstart": ["2020-01-01"],
        "contractend": ["2020-02-01"],
        "assignment": ["a0"],
    })

    def fake_radio(label, options, **kwargs):
        return options[0]

    with patch.dict(os.environ, {"EMAIL_SKIP_PRELOAD": "1"}), \
         patch("streamlit.sidebar.radio", side_effect=fake_radio):
        spec.loader.exec_module(email_module)

    # Ensure starting from a clean cache
    email_module.load_students.clear()
    email_module.load_ref_answers.clear()

    df_students1 = pd.DataFrame({"studentcode": ["s1"], "level": ["A1"]})
    df_ref1 = pd.DataFrame({"assignment": ["a1"]})

    def first_read_csv(url, *args, **kwargs):
        if url == email_module.STUDENTS_CSV_URL:
            return df_students1
        if url == email_module.REF_ANSWERS_CSV_URL:
            return df_ref1
        return pd.DataFrame()

    with patch.object(email_module, "read_csv_with_retry", side_effect=first_read_csv):
        first_students = email_module.load_students()
        first_ref = email_module.load_ref_answers()

    df_students2 = pd.DataFrame({"studentcode": ["s2"], "level": ["A2"]})
    df_ref2 = pd.DataFrame({"assignment": ["a2"]})

    def second_read_csv(url, *args, **kwargs):
        if url == email_module.STUDENTS_CSV_URL:
            return df_students2
        if url == email_module.REF_ANSWERS_CSV_URL:
            return df_ref2
        return pd.DataFrame()

    with patch.object(email_module, "read_csv_with_retry", side_effect=second_read_csv):
        # Cached data should still reflect first dataset
        cached_students = email_module.load_students()
        cached_ref = email_module.load_ref_answers()

    assert cached_students.equals(first_students)
    assert cached_ref.equals(first_ref)

    # Clearing caches should fetch the new dataset
    email_module.load_students.clear()
    email_module.load_ref_answers.clear()

    with patch.object(email_module, "read_csv_with_retry", side_effect=second_read_csv):
        refreshed_students = email_module.load_students()
        refreshed_ref = email_module.load_ref_answers()

    assert refreshed_students.equals(df_students2)
    assert refreshed_ref.equals(df_ref2)
