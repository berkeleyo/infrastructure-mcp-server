"""Regression checks for the eight MCP tool safety declarations."""

import ast
from pathlib import Path

EXPECTED = {
    "infrastructure_health": False,
    "discover_infrastructure": True,
    "detect_infrastructure_drift": True,
    "validate_infrastructure_config": False,
    "diagnose_dns": True,
    "diagnose_tls": True,
    "diagnose_http": True,
    "list_available_capabilities": False,
}


def test_every_mcp_tool_declares_all_four_safety_hints() -> None:
    source = Path(__file__).resolve().parents[1] / "src/infrastructure_mcp/server.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    functions = {
        node.name: node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)
    }
    for name, open_world in EXPECTED.items():
        decorators = functions[name].decorator_list
        matches = [
            decorator
            for decorator in decorators
            if isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "tool"
        ]
        assert len(matches) == 1, name
        annotations = next(k.value for k in matches[0].keywords if k.arg == "annotations")
        assert isinstance(annotations, ast.Call)
        assert isinstance(annotations.func, ast.Name)
        assert annotations.func.id == "ToolAnnotations"
        hints = {k.arg: ast.literal_eval(k.value) for k in annotations.keywords}
        assert hints == {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": open_world,
        }, name
