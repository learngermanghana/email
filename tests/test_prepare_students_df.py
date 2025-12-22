from pathlib import Path
from unittest.mock import patch
import importlib.util
import os

import pandas as pd


def _load_email_module():
    module_path = Path(__file__).resolve().parents[1] / "email.py"
    spec = importlib.util.spec_from_file_location("email_app", module_path)
    email_module = importlib.util.module_from_spec(spec)
    with patch.dict(os.environ, {"EMAIL_SKIP_PRELOAD": "1"}):
        spec.loader.exec_module(email_module)
    return email_module


def test_prepare_students_df_strips_nan_values():
    email_module = _load_email_module()

    raw = pd.DataFrame(
        {
            "StudentCode": ["s1", "s2"],
            "Name": [pd.NA, None],
            "ClassName": ["c1", "c1"],
            "Level": ["a1", "A1"],
        }
    )

    cleaned = email_module._prepare_students_df(raw)

    assert cleaned.loc[0, "name"] == ""
    assert cleaned.loc[1, "name"] == ""
    assert cleaned.loc[0, "studentcode"] == "s1"
    assert cleaned.loc[1, "level"] == "A1"
