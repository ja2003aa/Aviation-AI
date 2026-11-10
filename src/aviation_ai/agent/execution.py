"""
Tool Execution — parse, validate, and safely run registered tools (Lab 3).
"""

from __future__ import annotations

import ast
import json
import re
from typing import Any

from pydantic import ValidationError

from aviation_ai.agent.registry import TOOL_REGISTRY
from aviation_ai.agent.validation import GetFlightInfoArgs

_TOOL_CALL_RE = re.compile(
    r"<\|tool_call_start\|>(.*?)<\|tool_call_end\|>",
    re.DOTALL,
)
_JSON_CALL_RE = re.compile(
    r"\{[^{}]*\"name\"\s*:\s*\"[A-Za-z_][A-Za-z0-9_]*\"[^{}]*\}",
    re.DOTALL,
)


def parse_tool_calls(model_text: str) -> dict[str, Any]:
    """
    Parse tool calls from model text.

    Returns:
      {"calls": [...], "errors": [...]}
    Empty calls with no errors means the model did not request a tool.
    """
    calls: list[dict[str, Any]] = []
    errors: list[str] = []

    matches = list(_TOOL_CALL_RE.finditer(model_text or ""))
    for match in matches:
        body = match.group(1).strip()
        if not body:
            errors.append("Empty tool call between special tokens.")
            continue
        parsed = _parse_pythonic_call(body)
        if parsed is None:
            errors.append(f"Malformed tool call: {body[:120]}")
            continue
        calls.append(parsed)

    if calls or matches:
        return {"calls": calls, "errors": errors}

    for match in _JSON_CALL_RE.finditer(model_text or ""):
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            errors.append(f"Malformed JSON tool call: {match.group(0)[:120]}")
            continue
        name = payload.get("name")
        arguments = payload.get("arguments") or payload.get("parameters") or {}
        if not name:
            errors.append("JSON tool call missing name.")
            continue
        if not isinstance(arguments, dict):
            errors.append("JSON tool call arguments must be an object.")
            continue
        calls.append({"name": str(name), "arguments": arguments})

    return {"calls": calls, "errors": errors}


def _parse_pythonic_call(body: str) -> dict[str, Any] | None:
    text = body.strip()
    if not text.startswith("["):
        text = f"[{text}]"
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        return None

    node = tree.body
    if not isinstance(node, ast.List) or not node.elts:
        return None
    call = node.elts[0]
    if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
        return None
    if call.args:
        # Reject positional args to avoid arbitrary/unsafe calling patterns.
        return None

    arguments: dict[str, Any] = {}
    for keyword in call.keywords:
        if keyword.arg is None:
            return None
        try:
            arguments[keyword.arg] = ast.literal_eval(keyword.value)
        except (ValueError, TypeError):
            return None
    return {"name": call.func.id, "arguments": arguments}


def execute_tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Validate name + args, then execute only registered tools."""
    if name not in TOOL_REGISTRY:
        return {
            "error": f"Unknown tool: {name}",
            "available_tools": list(TOOL_REGISTRY.keys()),
        }

    # Whitelist: only get_flight_info is supported in this phase.
    if name != "get_flight_info":
        return {"error": f"Tool '{name}' is registered but not enabled."}

    try:
        args = GetFlightInfoArgs.model_validate(arguments or {})
    except ValidationError as exc:
        return {
            "error": "Invalid tool arguments",
            "details": json.loads(exc.json()),
        }

    return TOOL_REGISTRY[name](
        flight_number=args.flight_number,
        flight_date=args.flight_date,
    )
