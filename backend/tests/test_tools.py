import json

import pytest

from app.services.tool_registry import (
    TOOL_REGISTRY,
    assert_url_allowed,
    calculator,
    list_tools,
    run_python_sandboxed,
    safe_evaluate,
)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [("2 + 2", 4), ("2^10", 1024), ("sqrt(16) * 3", 12), ("10 % 3", 1), ("1e3 / 4", 250)],
)
def test_calculator_evaluates(expression: str, expected: float) -> None:
    assert safe_evaluate(expression) == expected


@pytest.mark.parametrize("expression", ["__import__('os')", "open('x')", "a.b", "x = 1"])
def test_calculator_rejects_unsafe_input(expression: str) -> None:
    with pytest.raises(ValueError):
        safe_evaluate(expression)


def test_tool_output_is_structured() -> None:
    result = json.loads(calculator.invoke({"expression": "3 * 7"}))
    assert result == {"tool_name": "calculator", "input": {"expression": "3 * 7"}, "output": 21, "error": None}


def test_code_executor_captures_stdout() -> None:
    result = run_python_sandboxed("print(sum(range(10)))", timeout_seconds=10)
    assert result["stdout"].strip() == "45"
    assert result["exit_code"] == 0


def test_code_executor_times_out() -> None:
    result = run_python_sandboxed("while True: pass", timeout_seconds=1)
    assert result["timed_out"] is True


async def test_ssrf_guard_blocks_private_addresses() -> None:
    for url in ("http://127.0.0.1/", "http://169.254.169.254/latest", "file:///etc/passwd"):
        with pytest.raises(ValueError):
            await assert_url_allowed(url)


def test_registry_lists_all_tools() -> None:
    names = {t.name for t in list_tools()}
    assert names == set(TOOL_REGISTRY) == {"web_search", "calculator", "code_executor", "json_api_call"}
