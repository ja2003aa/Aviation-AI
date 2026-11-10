"""
Conversation memory and context management (Lab 6).

Includes sliding-window history, current flight tracking, and a fidelity gate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

FLIGHT_MENTION_RE = re.compile(
    r"\b([A-Z]{2,3}\s?-?\s?\d{1,4}[A-Z]?)\b",
    re.IGNORECASE,
)
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


@dataclass
class ConversationMemory:
    """Per-session conversation state."""

    session_id: str = "default"
    messages: list[dict[str, str]] = field(default_factory=list)
    current_flight_number: str | None = None
    current_flight_date: str | None = None
    last_tool_facts: dict[str, Any] = field(default_factory=dict)
    window_size: int = 6

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        self.compact()

    def compact(self) -> None:
        """Sliding window + fidelity gate over essential flight facts (Lab 6)."""
        if len(self.messages) <= self.window_size:
            return
        summary = self._summary()
        if not self.fidelity_ok(summary):
            # Keep more recent turns if fidelity would lose essentials.
            self.messages = self.messages[-(self.window_size + 2) :]
            return
        recent = self.messages[-self.window_size :]
        self.messages = [{"role": "system", "content": f"Context summary: {summary}"}] + recent

    def _summary(self) -> str:
        parts = []
        if self.current_flight_number:
            parts.append(f"flight={self.current_flight_number}")
        if self.current_flight_date:
            parts.append(f"date={self.current_flight_date}")
        for key in ("terminal", "gate", "flight_status"):
            value = self.last_tool_facts.get(key)
            if value and value != "<not available>":
                parts.append(f"{key}={value}")
        return ", ".join(parts) if parts else "No essential flight facts yet."

    def fidelity_ok(self, summary: str) -> bool:
        """Ensure compact context still contains important known flight facts."""
        important: list[str] = []
        if self.current_flight_number:
            important.append(self.current_flight_number)
        if self.current_flight_date:
            important.append(self.current_flight_date)
        for key in ("terminal", "gate", "flight_status"):
            value = self.last_tool_facts.get(key)
            if value and value != "<not available>":
                important.append(str(value))
        return all(item in summary for item in important)

    def resolve_question(self, question: str) -> str:
        """Attach current flight context for follow-ups like 'its terminal'."""
        text = question.strip()
        mention = FLIGHT_MENTION_RE.search(text)
        date_mention = DATE_RE.search(text)

        if mention:
            self.current_flight_number = re.sub(r"[\s\-]+", "", mention.group(1).upper())
        if date_mention:
            self.current_flight_date = date_mention.group(1)

        follow_up = bool(
            re.search(r"\b(its|it|that flight|the flight|same flight)\b", text, re.I)
        ) or (
            self.current_flight_number
            and not mention
            and re.search(r"\b(gate|terminal|status|delayed|depart|arriv)\b", text, re.I)
        )

        if follow_up and self.current_flight_number and not mention:
            enriched = f"{text} (flight {self.current_flight_number}"
            if self.current_flight_date:
                enriched += f" on {self.current_flight_date}"
            enriched += ")"
            return enriched
        return text

    def update_from_tool_result(self, result: dict[str, Any]) -> None:
        if not result.get("found"):
            return
        flights = result.get("flights") or []
        if not flights:
            return
        flight = flights[0]
        self.current_flight_number = flight.get("flight_number") or self.current_flight_number
        self.last_tool_facts = {
            "terminal": flight.get("terminal"),
            "gate": flight.get("gate"),
            "flight_status": flight.get("flight_status"),
            "scheduled_time": flight.get("scheduled_time"),
            "direction": flight.get("direction"),
        }
        scheduled = flight.get("scheduled_time")
        if isinstance(scheduled, str) and len(scheduled) >= 10:
            self.current_flight_date = scheduled[:10]


# Separate memories for different sessions
_SESSIONS: dict[str, ConversationMemory] = {}


def get_memory(session_id: str = "default") -> ConversationMemory:
    if session_id not in _SESSIONS:
        _SESSIONS[session_id] = ConversationMemory(session_id=session_id)
    return _SESSIONS[session_id]


def reset_memory(session_id: str = "default") -> None:
    _SESSIONS[session_id] = ConversationMemory(session_id=session_id)
