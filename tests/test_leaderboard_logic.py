from __future__ import annotations

import importlib.util
import pathlib

import pandas as pd


spec = importlib.util.spec_from_file_location(
    "leaderboard_logic", pathlib.Path(__file__).resolve().parents[1] / "leaderboard_logic.py"
)
leaderboard_logic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(leaderboard_logic)


def test_dedupe_prefers_highest_score_then_latest_date():
    df = pd.DataFrame(
        {
            "StudentCode": ["s1", "s1", "s1"],
            "Name": ["Alice", "Alice", "Alice"],
            "Assignment": ["Essay 1", "Essay 1", "Essay 1"],
            "Score": [70, 95, 95],
            "Date": [
                pd.Timestamp("2024-01-03"),
                pd.Timestamp("2024-01-01"),
                pd.Timestamp("2024-01-02"),
            ],
            "Level": ["A1", "A1", "A1"],
        }
    )

    deduped = leaderboard_logic._dedupe_latest_attempt(df)

    assert len(deduped) == 1
    kept = deduped.iloc[0]
    assert kept["Score"] == 95
    assert kept["Date"] == pd.Timestamp("2024-01-02")
