"""
Flight collector facade — preserves older imports while using the board module.
"""

from __future__ import annotations

from dataclasses import dataclass

from aviation_ai.flights.board import (
    FLIGHTS_API_URL,
    FLIGHTS_PAGE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    FlightAPIError,
    FlightBoard,
    FlightInfoResult,
    ensure_board,
    get_board,
    get_flight_info,
    lookup_flights,
    normalize_flight_number,
    parse_flight,
    refresh_flights,
)
from aviation_ai.flights.models import FlightRecord

__all__ = [
    "FLIGHTS_API_URL",
    "FLIGHTS_PAGE_URL",
    "DEFAULT_TIMEOUT_SECONDS",
    "FlightAPIError",
    "FlightBoard",
    "FlightCollectionResult",
    "FlightInfoResult",
    "FlightRecord",
    "ensure_board",
    "fetch_flights",
    "get_board",
    "get_flight_info",
    "lookup_flights",
    "normalize_flight_number",
    "parse_flight",
    "refresh_flights",
]


@dataclass(frozen=True)
class FlightCollectionResult:
    source_page_url: str
    source_api_url: str
    retrieved_at_utc: str
    flights: list[FlightRecord]
    raw_count: int


def fetch_flights(
    *,
    limit: int | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> FlightCollectionResult:
    """Refresh once and optionally truncate the parsed list."""
    board = refresh_flights(timeout=timeout)
    flights = board.flights
    if limit is not None:
        flights = flights[: max(0, limit)]
    return FlightCollectionResult(
        source_page_url=board.source_page_url,
        source_api_url=board.source_api_url,
        retrieved_at_utc=board.last_refresh_utc or "",
        flights=flights,
        raw_count=board.raw_count,
    )
