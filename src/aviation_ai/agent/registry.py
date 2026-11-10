"""
Tool Registry — map tool names to real Python functions (Lab 3).
"""

from __future__ import annotations

from typing import Any, Callable

from aviation_ai.flights import FlightRecord, get_flight_info


def _flight_payload_for_llm(flight: FlightRecord) -> dict[str, Any]:
    display = flight.to_display_dict()
    # Per-flight notes list (do not share across flights).
    notes: list[str] = []
    if not flight.status_code:
        notes.append("Flight status is currently unavailable.")
    if not flight.gate:
        notes.append("Gate is currently unavailable.")
    return {
        "flight_number": display["flight_number"],
        "airline": display["airline"],
        "direction": display["direction"],
        "origin": display["origin"],
        "destination": display["destination"],
        "scheduled_time": display["scheduled_time"],
        "terminal": display["terminal"],
        "gate": display["gate"],
        "flight_status": display["status_code"],
        "notes": notes,
    }


def get_flight_info_tool(
    flight_number: str,
    flight_date: str | None = None,
) -> dict[str, Any]:
    result = get_flight_info(flight_number, date=flight_date)
    message = (
        "This flight is unavailable in the current airport feed."
        if not result.found
        else result.message
    )
    return {
        "found": result.found,
        "message": message,
        "query_flight_number": result.query_flight_number,
        "query_date": result.query_date,
        "flights": [_flight_payload_for_llm(f) for f in result.flights],
        "source_page_url": result.source_page_url,
        "source_api_url": result.source_api_url,
        "retrieved_at_utc": result.retrieved_at_utc,
        "from_cache": result.from_cache,
    }


TOOL_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {
    "get_flight_info": get_flight_info_tool,
}
