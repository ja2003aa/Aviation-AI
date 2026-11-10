"""Aviation AI — quick smoke demo for the improved agent."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from aviation_ai.agent import ask_agent, load_llm, reset_memory
from aviation_ai.flights import get_flight_info, refresh_flights


def main() -> None:
    board = refresh_flights()
    print(f"Board refreshed: {board.raw_count} flights at {board.last_refresh_utc}")
    sample = next(f for f in board.flights if f.flight_number)
    date = sample.scheduled_time[:10] if sample.scheduled_time else None
    info = get_flight_info(sample.flight_number, date)
    print("Lookup:", info.message)

    llm = load_llm()
    reset_memory("demo")
    q = f"What is the status of flight {sample.flight_number}"
    if date:
        q += f" on {date}"
    q += "?"
    turn = ask_agent(llm, q, session_id="demo")
    print("Final:", turn.final_answer)
    print("Trace:")
    print("\n".join(turn.trace))


if __name__ == "__main__":
    main()
