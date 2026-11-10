"""
Live KKIA flight board: refresh, retry, short cache, and safe lookup.

Separates API failures from "flight not found" results.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import requests

from aviation_ai.flights.models import FlightRecord

FLIGHTS_PAGE_URL = "https://www.kkia.sa/en/Flights/Departures-and-Arrivals"
FLIGHTS_API_URL = "https://www.kkia.sa/api/flightsInformation"
DEFAULT_TIMEOUT_SECONDS = 30
USER_AGENT = "AviationAI/1.0 (educational; on-demand refresh)"
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1.0
LOOKUP_CACHE_TTL_SECONDS = 60.0


class FlightAPIError(Exception):
    """Raised when the KKIA API request fails (not when a flight is missing)."""


@dataclass
class FlightInfoResult:
    query_flight_number: str
    query_date: str | None
    flights: list[FlightRecord]
    message: str
    source_page_url: str
    source_api_url: str
    retrieved_at_utc: str
    from_cache: bool = False

    @property
    def found(self) -> bool:
        return len(self.flights) > 0


@dataclass
class FlightBoard:
    """In-memory board with refresh metadata and a short-lived lookup cache."""

    flights: list[FlightRecord] = field(default_factory=list)
    raw_count: int = 0
    last_refresh_utc: str | None = None
    source_page_url: str = FLIGHTS_PAGE_URL
    source_api_url: str = FLIGHTS_API_URL
    _lookup_cache: dict[tuple[str, str | None], tuple[float, FlightInfoResult]] = field(
        default_factory=dict, repr=False
    )
    cache_hits: int = 0
    cache_misses: int = 0


_BOARD = FlightBoard()


def normalize_flight_number(flight_number: str) -> str:
    """Uppercase and strip spaces/hyphens/underscores for matching."""
    cleaned = re.sub(r"[\s\-_]+", "", (flight_number or "").upper())
    return cleaned


def _first_extra(raw: dict[str, Any]) -> dict[str, Any] | None:
    extras = raw.get("flightExtraData")
    if isinstance(extras, list) and extras and isinstance(extras[0], dict):
        return extras[0]
    return None


def _airport_label(airport: Any) -> str | None:
    if not isinstance(airport, dict):
        return None
    code = (airport.get("code") or "").strip()
    description = (airport.get("description") or airport.get("name") or "").strip()
    if code and description:
        return f"{description} ({code})"
    return description or code or None


def _compose_flight_number(raw: dict[str, Any], extra: dict[str, Any] | None) -> str | None:
    airline = raw.get("airline") if isinstance(raw.get("airline"), dict) else {}
    code = ((extra or {}).get("airlineCode") or airline.get("code") or "").strip()
    number = str(raw.get("number") or "").strip()
    suffix = str(raw.get("flightNumberSuffix") or "").strip()
    if not code and not number:
        return None
    return f"{code}{number}{suffix}"


def _status_code(raw: dict[str, Any], extra: dict[str, Any] | None) -> str | None:
    if extra:
        for key in ("flightStatus", "flightState"):
            value = extra.get(key)
            if value not in (None, ""):
                return str(value)
    remark = raw.get("remark")
    return str(remark) if remark not in (None, "") else None


def parse_flight(raw: dict[str, Any]) -> FlightRecord:
    extra = _first_extra(raw)
    airline_obj = raw.get("airline") if isinstance(raw.get("airline"), dict) else {}
    airline_name = (
        (extra or {}).get("airlineDescription")
        or airline_obj.get("translatedName")
        or airline_obj.get("description")
        or None
    )
    if isinstance(airline_name, str):
        airline_name = airline_name.strip() or None

    terminal = (
        raw.get("aircraftTerminal")
        or (extra or {}).get("publicTerminal")
        or (extra or {}).get("aircraftTerminal")
    )
    if isinstance(terminal, str):
        terminal = terminal.strip() or None

    gate = raw.get("passengerGate") or (extra or {}).get("passengerGate")
    if isinstance(gate, str):
        gate = gate.strip() or None
    elif gate is not None:
        gate = str(gate)

    direction = raw.get("departureOrArrival")
    if isinstance(direction, str):
        direction = direction.strip() or None

    scheduled = raw.get("scheduled")
    scheduled = scheduled.strip() if isinstance(scheduled, str) else None

    return FlightRecord(
        flight_number=_compose_flight_number(raw, extra),
        airline=airline_name,
        direction=direction,
        origin=_airport_label(raw.get("departureAirport")),
        destination=_airport_label(raw.get("arrivalAirport")),
        scheduled_time=scheduled,
        terminal=terminal,
        gate=gate,
        status_code=_status_code(raw, extra),
    )


def _fetch_once(timeout: float) -> list[dict[str, Any]]:
    response = requests.get(
        FLIGHTS_API_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise FlightAPIError(
            f"Unexpected payload type: {type(payload).__name__} (expected list)"
        )
    return payload


def refresh_flights(
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    retries: int = MAX_RETRIES,
    retry_delay: float = RETRY_DELAY_SECONDS,
) -> FlightBoard:
    """
    Refresh the board from KKIA with limited retries (Lab 2).

    Temporary network/HTTP issues are retried. Invalid permanent responses
    still raise FlightAPIError after attempts are exhausted.
    """
    last_error: Exception | None = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            payload = _fetch_once(timeout)
            flights = [parse_flight(item) for item in payload if isinstance(item, dict)]
            _BOARD.flights = flights
            _BOARD.raw_count = len(payload)
            _BOARD.last_refresh_utc = datetime.now(timezone.utc).isoformat()
            _BOARD._lookup_cache.clear()
            return _BOARD
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(retry_delay)
                continue
        except (ValueError, FlightAPIError, requests.RequestException) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(retry_delay)
                continue
    raise FlightAPIError(f"KKIA refresh failed after {retries} attempt(s): {last_error}")


def get_board() -> FlightBoard:
    return _BOARD


def ensure_board() -> FlightBoard:
    if not _BOARD.flights or not _BOARD.last_refresh_utc:
        refresh_flights()
    return _BOARD


def get_flight_info(
    flight_number: str,
    date: str | None = None,
    *,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> FlightInfoResult:
    """
    Search the current board by flight number (optional date).

    Missing flights return found=False. API failures raise FlightAPIError.
    """
    if force_refresh:
        refresh_flights()
    else:
        ensure_board()

    query = (flight_number or "").strip()
    needle = normalize_flight_number(query)
    date_filter = date.strip() if date else None
    cache_key = (needle, date_filter)

    if use_cache and cache_key in _BOARD._lookup_cache:
        stored_at, cached = _BOARD._lookup_cache[cache_key]
        if time.time() - stored_at <= LOOKUP_CACHE_TTL_SECONDS:
            _BOARD.cache_hits += 1
            return FlightInfoResult(
                query_flight_number=cached.query_flight_number,
                query_date=cached.query_date,
                flights=list(cached.flights),
                message=cached.message,
                source_page_url=cached.source_page_url,
                source_api_url=cached.source_api_url,
                retrieved_at_utc=cached.retrieved_at_utc,
                from_cache=True,
            )

    _BOARD.cache_misses += 1
    matches: list[FlightRecord] = []
    if needle:
        for flight in _BOARD.flights:
            if not flight.flight_number:
                continue
            if normalize_flight_number(flight.flight_number) != needle:
                continue
            if date_filter:
                if not flight.scheduled_time or not flight.scheduled_time.startswith(
                    date_filter
                ):
                    continue
            matches.append(flight)

    if not needle:
        message = "Please provide a flight number."
    elif not matches:
        message = "This flight is unavailable in the current airport feed."
    else:
        message = f"Found {len(matches)} matching flight(s) for {query}"
        if date_filter:
            message += f" on {date_filter}"
        message += "."
        missing_gates = sum(1 for f in matches if not f.gate)
        if missing_gates:
            message += f" Gate not available for {missing_gates} of them."

    result = FlightInfoResult(
        query_flight_number=query,
        query_date=date_filter,
        flights=matches,
        message=message,
        source_page_url=_BOARD.source_page_url,
        source_api_url=_BOARD.source_api_url,
        retrieved_at_utc=_BOARD.last_refresh_utc or "",
        from_cache=False,
    )
    if use_cache and needle:
        _BOARD._lookup_cache[cache_key] = (time.time(), result)
    return result


def lookup_flights(flight_number: str, date: str | None = None) -> list[FlightRecord]:
    return get_flight_info(flight_number, date).flights
