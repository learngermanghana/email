import ast
from pathlib import Path

import pandas as pd

SOURCE_PATH = Path(__file__).resolve().parents[1] / "email.py"
SOURCE = SOURCE_PATH.read_text()
MODULE_AST = ast.parse(SOURCE)
FUNCTION_NAMES = {"parse_datetime_flex", "parse_date_flex"}

selected_nodes = []
for node in MODULE_AST.body:
    if isinstance(node, ast.FunctionDef) and node.name in FUNCTION_NAMES:
        selected_nodes.append(node)

module = ast.Module(body=selected_nodes, type_ignores=[])
namespace = {"pd": pd, "datetime": __import__("datetime", fromlist=["datetime"]).datetime, "re": __import__("re")}
exec(compile(module, filename=str(SOURCE_PATH), mode="exec"), namespace)


def test_parse_datetime_flex_accepts_datetime_with_time():
    ts = namespace["parse_datetime_flex"]("10/13/2025 17:00:00")
    assert pd.notna(ts)
    assert ts == pd.Timestamp("2025-10-13 17:00:00")


def test_parse_date_flex_handles_datetime_with_time():
    result = namespace["parse_date_flex"]("10/13/2025 17:00:00")
    assert result == "2025-10-13"


def test_parse_datetime_flex_returns_nat_for_invalid():
    ts = namespace["parse_datetime_flex"]("not a date")
    assert pd.isna(ts)


def test_parse_datetime_flex_accepts_iso_with_z_suffix():
    ts = namespace["parse_datetime_flex"]("2025-12-21T22:08:01.624Z")
    assert pd.notna(ts)
    assert ts == pd.Timestamp("2025-12-21 22:08:01.624000+00:00")
