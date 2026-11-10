"""
Pydantic Validation — check tool arguments before Tool Execution (Lab 3).
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Airline code letters/digits + flight digits, optional suffix letter (e.g. XY330B)
_FLIGHT_RE = re.compile(r"^[A-Z0-9]{2,3}\d{1,4}[A-Z]?$", re.IGNORECASE)


class GetFlightInfoArgs(BaseModel):
    """Validated arguments for the get_flight_info tool."""

    flight_number: str = Field(min_length=2, description="Airline flight number such as SV1096")
    flight_date: str | None = Field(default=None, description="Optional date YYYY-MM-DD")

    @field_validator("flight_number")
    @classmethod
    def normalize_flight_number(cls, value: str) -> str:
        if value is None or not str(value).strip():
            raise ValueError("flight_number is required and cannot be empty")
        cleaned = re.sub(r"[\s\-_]+", "", str(value).strip().upper())
        if len(cleaned) < 2:
            raise ValueError("flight_number is too short")
        if not _FLIGHT_RE.match(cleaned):
            raise ValueError(
                "flight_number must look like SV1096 or XY330B (letters + digits)"
            )
        return cleaned

    @field_validator("flight_date")
    @classmethod
    def validate_optional_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        if cleaned == "":
            return None
        if not _DATE_RE.match(cleaned):
            raise ValueError("flight_date must be YYYY-MM-DD when provided")
        return cleaned
