"""
Parallel tool execution demo (Lab 3) using asyncio.gather / to_thread.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from aviation_ai.agent.registry import TOOL_REGISTRY


async def run_tool(tool_name: str, **kwargs: Any) -> Any:
    """Run a registry tool in a worker thread."""
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Unknown tool: {tool_name}"}
    return await asyncio.to_thread(TOOL_REGISTRY[tool_name], **kwargs)


async def parallel_flight_lookups(
    requests_list: list[dict[str, Any]],
    *,
    simulated_io_delay_s: float = 0.0,
) -> tuple[list[Any], float]:
    """
    Execute independent get_flight_info calls in parallel.

    If lookups are mostly in-memory, set simulated_io_delay_s > 0 to
    demonstrate the concept with a clearly labeled simulated delay.
    """

    async def one(req: dict[str, Any]) -> Any:
        if simulated_io_delay_s > 0:
            await asyncio.sleep(simulated_io_delay_s)
        return await run_tool(
            "get_flight_info",
            flight_number=req["flight_number"],
            flight_date=req.get("flight_date"),
        )

    start = time.perf_counter()
    results = await asyncio.gather(*(one(req) for req in requests_list))
    elapsed = time.perf_counter() - start
    return list(results), elapsed


def sequential_flight_lookups(
    requests_list: list[dict[str, Any]],
    *,
    simulated_io_delay_s: float = 0.0,
) -> tuple[list[Any], float]:
    start = time.perf_counter()
    results = []
    for req in requests_list:
        if simulated_io_delay_s > 0:
            time.sleep(simulated_io_delay_s)
        results.append(
            TOOL_REGISTRY["get_flight_info"](
                flight_number=req["flight_number"],
                flight_date=req.get("flight_date"),
            )
        )
    return results, time.perf_counter() - start
