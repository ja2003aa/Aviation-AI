"""
LLM Tool Calling with memory, max steps, loop detection, and tracing.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from aviation_ai.agent.execution import execute_tool_call, parse_tool_calls
from aviation_ai.agent.llm import LocalLLM
from aviation_ai.agent.memory import get_memory
from aviation_ai.agent.tool_schema import schemas_for_prompt
from aviation_ai.agent.tracing import TRACE, observe

SYSTEM_PROMPT_TEMPLATE = """You are Aviation AI for King Khalid International Airport (Riyadh / RUH).

Tool-call rules:
1. If the passenger message includes a flight number (e.g. SV1096, XY790, ZZ9999), call get_flight_info.
2. If they also give a date, pass flight_date as YYYY-MM-DD.
3. If there is NO flight number, do NOT call a tool. Reply exactly: "Please share your flight number (like SV1096) and I will look up the live information."
4. Prefer native format:
   <|tool_call_start|>[get_flight_info(flight_number="SV1096", flight_date="2026-11-11")]<|tool_call_end|>

Answer rules after a tool result:
1. Answer the passenger's specific question first.
2. Keep flight_status, gate, terminal, and scheduled_time separate.
3. If flight_status is "<not available>", say exactly: "Flight status is currently unavailable."
4. Translate status codes into plain language (OT → on time, DL → delayed, CX → cancelled). Never say "status code".
5. Never invent flight details. Use ONLY the tool result.
6. If found is false, say the flight is unavailable in the current airport feed.

List of tools: __TOOLS_JSON__
"""


@dataclass
class AgentTurnResult:
    question: str
    resolved_question: str
    raw_first_response: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    final_answer: str = ""
    used_tool: bool = False
    stopped_reason: str | None = None
    latency_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    trace: list[str] = field(default_factory=list)


def build_system_prompt() -> str:
    return SYSTEM_PROMPT_TEMPLATE.replace(
        "__TOOLS_JSON__", json.dumps(schemas_for_prompt())
    )


_STATUS_PLAIN = {
    "OT": "on time",
    "ON": "on time",
    "ON TIME": "on time",
    "DL": "delayed",
    "DELAY": "delayed",
    "DELAYED": "delayed",
    "ES": "delayed",
    "CX": "cancelled",
    "CANCEL": "cancelled",
    "CANCELLED": "cancelled",
    "CANCELED": "cancelled",
    "LD": "landed",
    "LANDED": "landed",
    "ARR": "arrived",
    "ARRIVED": "arrived",
    "DP": "departed",
    "DEP": "departed",
    "DEPARTED": "departed",
    "BD": "boarding",
    "BOARDING": "boarding",
    "GC": "gate closed",
    "DV": "diverted",
    "DIVERTED": "diverted",
    "FR": "in flight",
    "AIRBORNE": "in flight",
}


def plain_status(code: Any) -> str | None:
    if code is None or code == "" or code == "<not available>":
        return None
    raw = str(code).strip()
    key = raw.upper()
    if key in _STATUS_PLAIN:
        return _STATUS_PLAIN[key]
    if "CANCEL" in key:
        return "cancelled"
    if "DELAY" in key:
        return "delayed"
    if "BOARD" in key:
        return "boarding"
    if "LAND" in key:
        return "landed"
    if "DEPART" in key:
        return "departed"
    if "ARRIV" in key:
        return "arrived"
    if "DIVERT" in key:
        return "diverted"
    if "ON TIME" in key:
        return "on time"
    return raw.lower() if any(c.islower() for c in raw) or " " in raw else raw


def build_answer_reminder(question: str, tool_results: list[dict[str, Any]]) -> str:
    lines = [
        f'Passenger question: "{question}"',
        "Answer using ONLY the tool result in one short plain sentence.",
        "Do not invent details. Do not output JSON. Do not say status codes like OT.",
    ]
    if not tool_results:
        return " ".join(lines)
    payload = tool_results[0].get("result") or {}
    if payload.get("error"):
        lines.append(f'Tool error: {payload.get("error")}. Explain safely without inventing flights.')
        return " ".join(lines)
    if not payload.get("found"):
        lines.append(
            'found is false. Reply exactly: "This flight is unavailable in the current airport feed."'
        )
        return " ".join(lines)
    flights = payload.get("flights") or []
    if not flights:
        lines.append(
            'Reply exactly: "This flight is unavailable in the current airport feed."'
        )
        return " ".join(lines)
    flight = flights[0]
    q = question.lower()
    if "status" in q or "delayed" in q:
        label = plain_status(flight.get("flight_status"))
        if not label:
            lines.append('Reply exactly: "Flight status is currently unavailable."')
        elif "delayed" in q:
            if label == "delayed":
                lines.append(
                    f'Reply exactly: "Yes — flight {flight.get("flight_number")} is delayed."'
                )
            else:
                lines.append(
                    f'Reply exactly: "No — flight {flight.get("flight_number")} is {label}."'
                )
        else:
            lines.append(
                f'Reply exactly: "Flight {flight.get("flight_number")} is {label}."'
            )
        lines.append("Do not mention gate unless asked.")
    elif "gate" in q:
        if flight.get("gate") == "<not available>":
            lines.append("Say the gate is currently unavailable.")
        else:
            lines.append(f'Say the gate is {flight.get("gate")}.')
    elif "terminal" in q:
        lines.append(
            f'Say: "Flight {flight.get("flight_number")} is at terminal {flight.get("terminal")}."'
        )
    return " ".join(lines)


def _strip_special_tokens(text: str) -> str:
    cleaned = text
    for token in (
        "<|tool_call_start|>",
        "<|tool_call_end|>",
        "<|tool_response_start|>",
        "<|tool_response_end|>",
        "<|im_end|>",
        "<|im_start|>",
        "<|startoftext|>",
        "<|endoftext|>",
    ):
        cleaned = cleaned.replace(token, "")
    return cleaned.strip()


def _call_signature(name: str, arguments: dict[str, Any]) -> str:
    return json.dumps({"name": name, "arguments": arguments}, sort_keys=True)


@observe
def ask_agent(
    llm: LocalLLM,
    question: str,
    *,
    session_id: str = "default",
    max_steps: int = 3,
) -> AgentTurnResult:
    """
    Full agent turn with Lab 6 memory and Lab 7 max-steps / loop detection.
    """
    start = time.time()
    TRACE.clear()
    TRACE.record("passenger_question_received", question)

    memory = get_memory(session_id)
    resolved = memory.resolve_question(question)
    memory.add("user", question)
    TRACE.record("context_resolved", resolved)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": resolved},
    ]
    input_tokens = llm.count_tokens(resolved)
    first = llm.generate(messages, max_new_tokens=256)
    output_tokens = llm.count_tokens(first)

    result = AgentTurnResult(
        question=question,
        resolved_question=resolved,
        raw_first_response=first,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    parsed = parse_tool_calls(first)
    calls = parsed["calls"]
    if parsed["errors"]:
        TRACE.record("tool_parse_errors", "; ".join(parsed["errors"]))
        if not calls:
            result.final_answer = (
                "I could not read a valid tool call. "
                "Please rephrase with a clear flight number like SV1096."
            )
            result.stopped_reason = "malformed_tool_call"
            result.latency_s = time.time() - start
            result.trace = TRACE.as_lines()
            memory.add("assistant", result.final_answer)
            return result

    if not calls:
        result.final_answer = _strip_special_tokens(first)
        result.latency_s = time.time() - start
        result.trace = TRACE.as_lines()
        memory.add("assistant", result.final_answer)
        return result

    result.used_tool = True
    seen_calls: set[str] = set()
    steps = 0

    while calls and steps < max_steps:
        steps += 1
        call = calls[0]
        name = call["name"]
        arguments = call.get("arguments") or {}
        signature = _call_signature(name, arguments)
        TRACE.record("tool_selected", name)
        TRACE.record("arguments_received", json.dumps(arguments))

        if signature in seen_calls:
            TRACE.record("loop_detected", signature)
            result.stopped_reason = "loop_detected"
            result.final_answer = (
                "Stopped: repeated identical tool call detected. "
                "Please ask a new question or request a refresh."
            )
            break
        seen_calls.add(signature)

        tool_payload = execute_tool_call(name, arguments)
        TRACE.record("tool_executed", name)
        TRACE.record("result_retrieved", str(tool_payload.get("found", tool_payload.get("error"))))
        result.tool_calls.append(call)
        result.tool_results.append(
            {"name": name, "arguments": arguments, "result": tool_payload}
        )

        if name == "get_flight_info" and isinstance(tool_payload, dict):
            memory.update_from_tool_result(tool_payload)

        messages.append({"role": "assistant", "content": first if steps == 1 else first})
        messages.append(
            {
                "role": "tool",
                "name": name,
                "content": json.dumps(tool_payload, ensure_ascii=False),
            }
        )
        messages.append(
            {
                "role": "user",
                "content": build_answer_reminder(resolved, result.tool_results),
            }
        )
        first = llm.generate(messages, max_new_tokens=200)
        output_tokens += llm.count_tokens(first)
        parsed = parse_tool_calls(first)
        calls = parsed["calls"]
        # After one successful tool answer, stop unless model emits another call.
        if not calls:
            result.final_answer = _strip_special_tokens(first)
            TRACE.record("final_answer_generated", result.final_answer[:120])
            break
    else:
        if steps >= max_steps and not result.final_answer:
            result.stopped_reason = "max_steps"
            result.final_answer = (
                f"Stopped safely after reaching max_steps={max_steps}."
            )

    if not result.final_answer:
        result.final_answer = _strip_special_tokens(first)

    result.output_tokens = output_tokens
    result.latency_s = time.time() - start
    result.trace = TRACE.as_lines()
    memory.add("assistant", result.final_answer)
    return result
