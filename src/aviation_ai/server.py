"""
LLM agent HTTP API for the web UI.

Loads LiquidAI/LFM2.5-1.2B-Instruct once and serves /chat via the same
ask_agent tool-calling loop used in the notebook / main.py.

Run:
  source .venv/bin/activate
  uvicorn aviation_ai.server:app --reload --port 8000
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from aviation_ai.agent.agent import ask_agent
from aviation_ai.agent.llm import LocalLLM, load_llm

app = FastAPI(title="Aviation AI Agent", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_llm: LocalLLM | None = None


def get_llm() -> LocalLLM:
    global _llm
    if _llm is None:
        _llm = load_llm()
    return _llm


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str = "web"


class ChatResponse(BaseModel):
    reply: str
    used_tool: bool
    session_id: str
    latency_s: float
    stopped_reason: str | None = None
    tool_result: dict[str, Any] | None = None
    source: str = "lfm2.5-local"


@app.on_event("startup")
def warmup() -> None:
    # Fail fast on bad installs; model download can take a while the first time.
    get_llm()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model": get_llm().model_id}


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    question = body.message.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Please enter a message.")

    result = ask_agent(get_llm(), question, session_id=body.session_id)
    tool_result = None
    if result.tool_results:
        last = result.tool_results[-1].get("result") or {}
        flights = last.get("flights") or []
        tool_result = {
            "found": last.get("found"),
            "message": last.get("message"),
            "flight": flights[0] if flights else None,
            "retrieved_at_utc": last.get("retrieved_at_utc"),
            "source": last.get("source_page_url") or last.get("source_api_url"),
        }

    return ChatResponse(
        reply=result.final_answer,
        used_tool=result.used_tool,
        session_id=body.session_id,
        latency_s=result.latency_s,
        stopped_reason=result.stopped_reason,
        tool_result=tool_result,
    )
