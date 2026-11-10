"""Flight information retrieval (gates, terminals, status, times)."""

from aviation_ai.flights.collector import (
    FLIGHTS_API_URL,
    FLIGHTS_PAGE_URL,
    FlightAPIError,
    FlightBoard,
    FlightCollectionResult,
    FlightInfoResult,
    ensure_board,
    fetch_flights,
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
