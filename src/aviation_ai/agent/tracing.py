"""
Simple execution tracing inspired by Lab 7's @observe decorator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable


@dataclass
class TraceEvent:
    step: str
    detail: str
    at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


@dataclass
class TraceLog:
    events: list[TraceEvent] = field(default_factory=list)

    def record(self, step: str, detail: str = "") -> None:
        self.events.append(TraceEvent(step=step, detail=detail))

    def as_lines(self) -> list[str]:
        return [f"[{e.at}] {e.step}: {e.detail}" for e in self.events]

    def clear(self) -> None:
        self.events.clear()


TRACE = TraceLog()


def observe(func: Callable[..., Any]) -> Callable[..., Any]:
    """Minimal @observe wrapper (Lab 7)."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        TRACE.record("trace_started", func.__name__)
        try:
            result = func(*args, **kwargs)
            TRACE.record("trace_completed", func.__name__)
            return result
        except Exception as exc:  # noqa: BLE001 - surface in trace then re-raise
            TRACE.record("trace_failed", f"{func.__name__}: {exc}")
            raise

    return wrapper
