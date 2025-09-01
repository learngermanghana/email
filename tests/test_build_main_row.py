import ast
from pathlib import Path
from datetime import date

import pandas as pd
import pytest


def get_build_main_row():
    source = (Path(__file__).resolve().parents[1] / "email.py").read_text()
    module_ast = ast.parse(source)
    funcs = []

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            if node.name in {"_safe_str", "build_main_row"}:
                funcs.append(node)
            self.generic_visit(node)

    Visitor().visit(module_ast)
    module = ast.Module(body=funcs, type_ignores=[])
    ns = {
        "pd": pd,
        "clean_phone_gh": lambda x: x,
        "parse_date_flex": lambda x: x,
        "date": date,
        "Any": __import__("typing").Any,
        "TARGET_COLUMNS": [
            "Name", "Phone", "Location", "Level", "Paid", "Balance",
            "ContractStart", "ContractEnd", "StudentCode", "Email",
            "Emergency Contact (Phone Number)", "Status", "EnrollDate",
            "ClassName",
        ],
        "col_lookup_df": {},
    }
    exec(compile(module, filename="email.py", mode="exec"), ns)
    return ns["build_main_row"], ns


build_main_row, ns = get_build_main_row()


@pytest.mark.parametrize("bad_value", [None, float("nan"), 123])
def test_build_main_row_non_string_inputs(bad_value):
    src_row = {
        "name": bad_value,
        "location": bad_value,
        "email": bad_value,
        "studentcode": bad_value,
        "status": bad_value,
        "classname": bad_value,
        "phone": "0241234567",
        "level": "b2",
        "paid": "",
        "balance": "",
        "contractstart": "2024-01-01",
        "contractend": "",
        "enrolldate": "",
    }
    ns["col_lookup_df"] = {k: k for k in src_row}
    row = build_main_row(src_row)

    assert row["Name"] == ""
    assert row["Location"] == ""
    assert row["Email"] == ""
    assert row["StudentCode"] == ""
    assert row["Status"] == "Active"
    assert row["ClassName"] == "B2"
