import ast
import pathlib
import textwrap


def get_wrap_template_lines():
    source = (pathlib.Path(__file__).resolve().parents[1] / "app.py").read_text()
    module_ast = ast.parse(source)
    func_node = next(
        node for node in module_ast.body if isinstance(node, ast.FunctionDef) and node.name == "wrap_template_lines"
    )
    module = ast.Module(body=[func_node], type_ignores=[])
    code = compile(module, filename="app.py", mode="exec")
    ns = {"textwrap": textwrap, "AGREEMENT_LINE_LIMIT": 120}
    exec(code, ns)
    return ns["wrap_template_lines"]


wrap_template_lines = get_wrap_template_lines()


def test_wraps_line_without_spaces():
    long_line = "A" * 130
    wrapped, warnings = wrap_template_lines(long_line)
    assert warnings == [1]
    assert wrapped == "A" * 120 + "\n" + "A" * 10


def test_ignores_lines_with_spaces():
    line = "A" * 100 + " B"
    wrapped, warnings = wrap_template_lines(line)
    assert warnings == []
    assert wrapped == line

