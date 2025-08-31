import ast
import pathlib
import re


def get_clean_phone():
    source = (pathlib.Path(__file__).resolve().parents[1] / "app.py").read_text()
    module_ast = ast.parse(source)
    func_node = next(
        node for node in module_ast.body if isinstance(node, ast.FunctionDef) and node.name == "clean_phone"
    )
    module = ast.Module(body=[func_node], type_ignores=[])
    code = compile(module, filename="app.py", mode="exec")
    ns = {"re": re}
    exec(code, ns)
    return ns["clean_phone"]

clean_phone = get_clean_phone()


def test_clean_phone_handles_missing_zero():
    assert clean_phone("241234567") == "233241234567"
    assert clean_phone("512345678") == "233512345678"
    assert clean_phone("912345678") == "233912345678"


def test_clean_phone_invalid_9_digit_number():
    assert clean_phone("123456789") is None


def test_clean_phone_existing_formats():
    assert clean_phone("+233241234567") == "233241234567"
    assert clean_phone("0241234567") == "233241234567"
