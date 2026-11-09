"""Built-in agent tools.

Every tool returns a JSON string with the same structure, so the frontend can
render tool calls generically and the LLM always sees consistent observations:

    {"tool_name": "...", "input": {...}, "output": ..., "error": null}
"""

import asyncio
import ipaddress
import json
import math
import re
import signal
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from langchain_core.tools import BaseTool, tool

from app.config import get_settings
from app.core.logging import get_logger
from app.models.agent import ToolInfo

logger = get_logger(__name__)

_MAX_OUTPUT_CHARS = 8_000


def tool_result(tool_name: str, tool_input: dict[str, Any], output: Any = None, error: str | None = None) -> str:
    return json.dumps(
        {"tool_name": tool_name, "input": tool_input, "output": output, "error": error},
        default=str,
        ensure_ascii=False,
    )


def _truncate(text: str, limit: int = _MAX_OUTPUT_CHARS) -> str:
    return text if len(text) <= limit else f"{text[:limit]}\n... [truncated {len(text) - limit} chars]"


# --------------------------------------------------------------------- web search
def _ddg_search(query: str, max_results: int) -> list[dict[str, str]]:
    try:  # the package was renamed to `ddgs`; support both.
        from ddgs import DDGS  # type: ignore[import-not-found]
    except ImportError:
        from duckduckgo_search import DDGS

    with DDGS() as ddgs:
        results = ddgs.text(query, max_results=max_results) or []
    return [
        {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
        for r in results
    ]


@tool("web_search")
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web with DuckDuckGo. Use for current events, facts you are unsure
    about, or anything that needs up-to-date information. Returns titles, URLs and snippets."""
    args = {"query": query, "max_results": max_results}
    try:
        results = _ddg_search(query, max(1, min(max_results, 10)))
        return tool_result("web_search", args, results)
    except Exception as exc:
        logger.warning("web_search_failed", error=str(exc))
        return tool_result("web_search", args, error=f"Search failed: {exc}")


# --------------------------------------------------------------------- calculator
_CALC_ALLOWED_CHARS = re.compile(r"^[0-9a-z_\s\.\+\-\*/%\(\),<>=!&|~]*$")
_CALC_ALLOWED_NAMES = frozenset(
    {
        "sin", "cos", "tan", "arcsin", "arccos", "arctan", "arctan2",
        "sinh", "cosh", "tanh", "arcsinh", "arccosh", "arctanh",
        "sqrt", "exp", "expm1", "log", "log10", "log1p", "abs", "where",
        "pi", "e",
    }
)


def safe_evaluate(expression: str) -> float | int | bool:
    """Evaluate a math expression with numexpr after strict whitelisting.

    Raises:
        ValueError: if the expression contains disallowed characters or names.
    """
    import numexpr

    expr = expression.strip().lower().replace("^", "**")
    if not expr:
        raise ValueError("Empty expression")
    if len(expr) > 500:
        raise ValueError("Expression too long (max 500 chars)")
    if not _CALC_ALLOWED_CHARS.match(expr):
        raise ValueError("Expression contains unsupported characters")
    # Ignore the exponent marker inside numeric literals like 1e-5.
    names = set(re.findall(r"(?<![0-9.])[a-z_][a-z0-9_]*", expr))
    unknown = names - _CALC_ALLOWED_NAMES
    if unknown:
        raise ValueError(f"Unsupported names: {', '.join(sorted(unknown))}")

    value = numexpr.evaluate(expr, local_dict={"pi": math.pi, "e": math.e}, global_dict={})
    result = value.item() if hasattr(value, "item") else value
    if isinstance(result, float) and result.is_integer() and abs(result) < 1e15:
        return int(result)
    return result


@tool("calculator")
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression precisely, e.g. "sqrt(2) * (3 + 4)^2" or
    "log10(1000)". Supports + - * / % ** ^, parentheses, trig/log/exp functions, pi and e.
    Always use this instead of doing arithmetic in your head."""
    args = {"expression": expression}
    try:
        return tool_result("calculator", args, safe_evaluate(expression))
    except Exception as exc:
        return tool_result("calculator", args, error=str(exc))


# ------------------------------------------------------------------ code executor
_SANDBOX_BOOTSTRAP = textwrap.dedent(
    """
    import resource, runpy, sys
    limits = {{
        "RLIMIT_CPU": ({cpu}, {cpu}),
        "RLIMIT_AS": ({mem}, {mem}),
        "RLIMIT_FSIZE": ({fsize}, {fsize}),
        "RLIMIT_NOFILE": (64, 64),
    }}
    for name, value in limits.items():
        try:
            resource.setrlimit(getattr(resource, name), value)
        except (ValueError, OSError, AttributeError):
            pass  # not supported on this platform (e.g. RLIMIT_AS on macOS)
    sys.argv = ["main.py"]
    runpy.run_path("main.py", run_name="__main__")
    """
)


def run_python_sandboxed(code: str, timeout_seconds: int) -> dict[str, Any]:
    """Run code in a separate, isolated Python process with resource limits.

    Isolation: `-I` (no env vars / user site-packages), a throwaway working dir,
    a minimal environment, CPU/memory/file-size rlimits and a wall-clock timeout.
    NOTE: this is defence-in-depth, not a security boundary. Use gVisor, Firecracker
    or a dedicated container for running untrusted code in production.
    """
    bootstrap = _SANDBOX_BOOTSTRAP.format(
        # CPU limit sits above the wall-clock timeout so the timeout normally fires first.
        cpu=timeout_seconds + 1, mem=512 * 1024 * 1024, fsize=10 * 1024 * 1024
    )
    with tempfile.TemporaryDirectory(prefix="agentforge-exec-") as workdir:
        Path(workdir, "main.py").write_text(code, encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-B", "-c", bootstrap],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONIOENCODING": "utf-8", "HOME": workdir},
                stdin=subprocess.DEVNULL,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            return {"stdout": _truncate(stdout), "stderr": "", "exit_code": None, "timed_out": True}
    return {
        "stdout": _truncate(proc.stdout),
        "stderr": _truncate(proc.stderr, 4_000),
        "exit_code": proc.returncode,
        # Killed by RLIMIT_CPU (SIGXCPU) or the kernel (SIGKILL) => treat as a timeout.
        "timed_out": proc.returncode in (-signal.SIGXCPU, -signal.SIGKILL),
    }


@tool("code_executor")
def code_executor(code: str) -> str:
    """Execute Python 3 code in a sandboxed subprocess and return stdout, stderr and the
    exit code. Use print() to produce output. Only the standard library (plus numpy if
    installed) is available; there is no network or persistent filesystem. Has a time limit."""
    args = {"code": code}
    timeout = get_settings().code_exec_timeout_seconds
    try:
        result = run_python_sandboxed(code, timeout)
    except Exception as exc:
        return tool_result("code_executor", args, error=f"Execution failed: {exc}")
    error = f"Timed out after {timeout}s" if result["timed_out"] else None
    return tool_result("code_executor", args, result, error=error)


# ------------------------------------------------------------------- JSON API call
def _is_public_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
        or ip.is_multicast or ip.is_unspecified
    )


async def assert_url_allowed(url: str) -> None:
    """Basic SSRF protection: http(s) only and no private/loopback destinations."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only absolute http(s) URLs are allowed")
    if get_settings().allow_private_network_api_calls:
        return
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(parsed.hostname, parsed.port or None)
    addresses = {info[4][0] for info in infos}
    if not addresses or not all(_is_public_ip(a) for a in addresses):
        raise ValueError("Requests to private, loopback or internal addresses are blocked")


@tool("json_api_call")
async def json_api_call(
    url: str,
    method: Literal["GET", "POST"] = "GET",
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> str:
    """Call an HTTP JSON API. Use GET to fetch data or POST with a JSON `body` to send
    data. Returns the status code and parsed JSON (or text) response."""
    args = {"url": url, "method": method, "body": body}
    settings = get_settings()
    try:
        await assert_url_allowed(url)
        async with httpx.AsyncClient(timeout=settings.api_call_timeout_seconds, follow_redirects=False) as client:
            response = await client.request(
                method,
                url,
                json=body if method == "POST" else None,
                headers={"User-Agent": "AgentForge/1.0", "Accept": "application/json", **(headers or {})},
            )
        try:
            payload: Any = response.json()
            serialized = json.dumps(payload, ensure_ascii=False)
            if len(serialized) > _MAX_OUTPUT_CHARS:
                payload = _truncate(serialized)
        except ValueError:
            payload = _truncate(response.text)
        return tool_result(
            "json_api_call",
            args,
            {
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type"),
                "body": payload,
            },
        )
    except Exception as exc:
        return tool_result("json_api_call", args, error=str(exc))


# ----------------------------------------------------------------------- registry
TOOL_REGISTRY: dict[str, BaseTool] = {t.name: t for t in (web_search, calculator, code_executor, json_api_call)}


def get_tools(names: list[str]) -> list[BaseTool]:
    return [TOOL_REGISTRY[name] for name in names if name in TOOL_REGISTRY]


def list_tools() -> list[ToolInfo]:
    return [
        ToolInfo(name=t.name, description=" ".join((t.description or "").split()), parameters=t.args)
        for t in TOOL_REGISTRY.values()
    ]
