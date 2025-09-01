import ast
import pathlib
import pandas as pd


def get_col_lookup():
    source = (pathlib.Path(__file__).resolve().parents[1] / "email.py").read_text()
    module_ast = ast.parse(source)
    func_node = next(
        node for node in module_ast.body if isinstance(node, ast.FunctionDef) and node.name == "col_lookup"
    )
    module = ast.Module(body=[func_node], type_ignores=[])
    code = compile(module, filename="email.py", mode="exec")
    ns = {"pd": pd}
    exec(code, ns)
    return ns["col_lookup"]

col_lookup = get_col_lookup()


def test_col_lookup_existing_column():
    df = pd.DataFrame(columns=["Student Code", "Balance Due"])
    assert col_lookup(df, "studentcode") == "Student Code"
    assert col_lookup(df, "BALANCE_DUE") == "Balance Due"


def test_col_lookup_missing_column_returns_default():
    df = pd.DataFrame(columns=["A"])
    assert col_lookup(df, "missing", default="fallback") == "fallback"
    assert col_lookup(df, "another_missing") is None
