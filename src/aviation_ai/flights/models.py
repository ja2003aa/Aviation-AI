"""Typed flight records — only fields present in the KKIA public feed."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FlightRecord:
    """One flight as returned by KKIA (missing fields stay None)."""

    flight_number: str | None
    airline: str | None
    direction: str | None  # "Departure" or "Arrival" when provided
    origin: str | None
    destination: str | None
    scheduled_time: str | None
    terminal: str | None
    gate: str | None
    status_code: str | None  # raw code from the feed; never invented

    def to_display_dict(self) -> dict[str, Any]:
        """Serialize for printing; None becomes an explicit missing marker."""
        out: dict[str, Any] = {}
        for key, value in asdict(self).items():
            out[key] = value if value not in (None, "") else "<not available>"
        return out
