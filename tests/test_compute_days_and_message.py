import ast
import pathlib

import pandas as pd


def load_namespace():
    source = (pathlib.Path(__file__).resolve().parents[1] / "email.py").read_text()
    module_ast = ast.parse(source)
    func_nodes = [
        node
        for node in ast.walk(module_ast)
        if isinstance(node, ast.FunctionDef) and node.name == "compute_days_and_message"
    ]
    mod = ast.Module(body=func_nodes, type_ignores=[])
    ast.fix_missing_locations(mod)
    code = compile(mod, filename="email.py", mode="exec")
    ns = {"pd": pd}
    exec(code, ns)
    return ns


def test_compute_days_and_message_handles_missing_days_left():
    ns = load_namespace()
    compute_days_and_message = ns["compute_days_and_message"]

    row = pd.Series({"days_left": float("nan")})
    days, msg = compute_days_and_message(row["days_left"], "GHS 0.00")

    assert days == "N/A"
    assert "balance" in msg.lower()
