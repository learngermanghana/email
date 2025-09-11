import ast
import pathlib

import pandas as pd


def load_rank_students():
    source = (pathlib.Path(__file__).resolve().parents[1] / "email.py").read_text()
    module_ast = ast.parse(source)
    func_nodes = [
        node
        for node in ast.walk(module_ast)
        if isinstance(node, ast.FunctionDef) and node.name == "rank_students"
    ]
    mod = ast.Module(body=func_nodes, type_ignores=[])
    ast.fix_missing_locations(mod)
    code = compile(mod, filename="email.py", mode="exec")
    ns = {"pd": pd}
    exec(code, ns)
    return ns["rank_students"]


def test_rank_students_counts():
    rank_students = load_rank_students()
    csv_path = pathlib.Path(__file__).parent / "data" / "leaderboard_sample.csv"
    df = pd.read_csv(csv_path)
    ranked = rank_students(df, min_assign=1)

    alice = ranked[ranked["studentcode"] == "S1"].iloc[0]
    bob = ranked[ranked["studentcode"] == "S2"].iloc[0]

    assert alice["completed"] == 3
    assert alice["total_score"] == 23
    assert bob["completed"] == 1
    assert bob["total_score"] == 7
