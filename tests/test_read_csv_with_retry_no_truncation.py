import ast
import pathlib
from io import BytesIO
import pandas as pd


def load_functions():
    source = (pathlib.Path(__file__).resolve().parents[1] / "email.py").read_text()
    module_ast = ast.parse(source)
    func_nodes = [
        node
        for node in ast.walk(module_ast)
        if isinstance(node, ast.FunctionDef) and node.name in {"read_csv_with_retry", "rank_students"}
    ]
    mod = ast.Module(body=func_nodes, type_ignores=[])
    ast.fix_missing_locations(mod)
    ns = {"pd": pd, "BytesIO": BytesIO}
    exec(compile(mod, filename="email.py", mode="exec"), ns)
    return ns


def test_read_csv_with_retry_no_truncation():
    ns = load_functions()
    read_csv_with_retry = ns["read_csv_with_retry"]
    rank_students = ns["rank_students"]

    csv_lines = ["studentcode,name,assignment,score"]
    for i in range(10):
        csv_lines.append(f"S1,Alice,HW{i},1")
    csv_data = "\n".join(csv_lines).encode("utf-8")

    ns["fetch_url"] = lambda url: csv_data

    df = read_csv_with_retry("http://example.com")
    assert len(df) == 10

    ranked = rank_students(df, min_assign=1)
    alice = ranked[ranked["studentcode"] == "S1"].iloc[0]
    assert alice["completed"] == 10
