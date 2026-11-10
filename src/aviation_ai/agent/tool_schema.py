"""
Tool Schema — describes tools the LLM may call.

Same idea as Lab 3 Code 2: a JSON schema the model reads to decide
when to call a tool and which arguments to pass.
"""

from __future__ import annotations

from typing import Any

# OpenAI-style function schema (also used by LiquidAI LFM2.5 tool prompts).
GET_FLIGHT_INFO_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_flight_info",
        "description": (
            "Look up live King Khalid International Airport (Riyadh / RUH) "
            "flight information by flight number. Call this tool for questions "
            "about a specific flight's status, gate, terminal, scheduled time, "
            "origin, destination, arrival, or departure. Do not invent flight data. "
            "If the passenger did not provide a flight number, do not call this tool."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "flight_number": {
                    "type": "string",
                    "description": (
                        "Airline flight number, e.g. SV1096 or XY330B. "
                        "Spaces are allowed (e.g. 'SV 1096')."
                    ),
                },
                "flight_date": {
                    "type": "string",
                    "description": (
                        "Optional scheduled date as YYYY-MM-DD. "
                        "Omit this argument if the passenger did not mention a date."
                    ),
                },
            },
            "required": ["flight_number"],
        },
    },
}

# List passed to the LLM (extend later with more tools).
TOOL_SCHEMAS: list[dict[str, Any]] = [GET_FLIGHT_INFO_TOOL]


def schemas_for_prompt() -> list[dict[str, Any]]:
    """Compact tool list for the system prompt (name/description/parameters)."""
    return [tool["function"] for tool in TOOL_SCHEMAS]
