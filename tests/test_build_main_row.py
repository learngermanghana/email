import ast
import pathlib
from datetime import date

import pandas as pd
import pytest


def load_namespace():
    source = (pathlib.Path(__file__).resolve().parents[1] / "email.py").read_text()
    module_ast = ast.parse(source)
    func_nodes = [
        node
        for node in ast.walk(module_ast)
        if isinstance(node, ast.FunctionDef) and node.name in {"parse_date_flex", "build_main_row"}
    ]
    mod = ast.Module(body=func_nodes, type_ignores=[])
    ast.fix_missing_locations(mod)
    code = compile(mod, filename="email.py", mode="exec")
    ns = {"pd": pd, "date": date}
    exec(code, ns)
    return ns


@pytest.mark.parametrize("header", ["EnrollDate", "Enroll_Date"])
def test_build_main_row_enroll_date_headers(header):
    ns = load_namespace()
    ns["clean_phone_gh"] = lambda x: x  # minimal stub
    ns["TARGET_COLUMNS"] = ["EnrollDate"]

    if header == "EnrollDate":
        ns["col_lookup_df"] = {"enrolldate": "EnrollDate"}
    else:
        ns["col_lookup_df"] = {"enroll_date": "Enroll_Date"}

    build_main_row = ns["build_main_row"]
    src = {header: "2024-02-03"}
    result = build_main_row(src)
    assert result["EnrollDate"] == "2024-02-03"
