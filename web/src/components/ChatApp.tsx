"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { fetchBoardInBrowser } from "@/lib/boardClient";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

const SAMPLE_QUERIES = [
  "What is the status of flight XY790?",
  "Which terminal is flight SV1096?",
  "What is the gate for flight XY054?",
  "Where is flight ZZ9999 on 2099-01-01?",
];

const QUICK_CHIPS = [
  "What is its terminal?",
  "What is its gate?",
  "What is the status?",
];

function PlaneIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"
      />
    </svg>
  );
}

async function typeReply(
  fullText: string,
  onUpdate: (partial: string) => void
): Promise<void> {
  const text = fullText || "";
  let index = 0;
  // Faster for short replies, a bit slower for longer ones — ChatGPT-like feel.
  const step = text.length > 120 ? 3 : 2;
  const delay = text.length > 180 ? 12 : 16;

  return new Promise((resolve) => {
    const tick = () => {
      index = Math.min(text.length, index + step);
      onUpdate(text.slice(0, index));
      if (index >= text.length) {
        resolve();
        return;
      }
      window.setTimeout(tick, delay);
    };
    tick();
  });
}

export default function ChatApp() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Welcome aboard. I’m Aviation AI for King Khalid International Airport — ask about a flight’s status, terminal, or gate and I’ll check the live board.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [showWelcomeSuggestions, setShowWelcomeSuggestions] = useState(true);
  const [currentFlightNumber, setCurrentFlightNumber] = useState<string | null>(
    null
  );
  const [currentFlightDate, setCurrentFlightDate] = useState<string | null>(
    null
  );
  const [sessionId] = useState(() => crypto.randomUUID());
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;

    setShowWelcomeSuggestions(false);
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "user", content: trimmed },
    ]);
    setInput("");
    setBusy(true);

    const assistantId = crypto.randomUUID();
    setMessages((prev) => [
      ...prev,
      {
        id: assistantId,
        role: "assistant",
        content: "",
        streaming: true,
      },
    ]);

    try {
      // Fetch live board in the browser — KKIA allows CORS but blocks many Vercel IPs.
      const boardPayload = await fetchBoardInBrowser();

      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: trimmed,
          sessionId,
          currentFlightNumber,
          currentFlightDate,
          boardPayload,
        }),
      });
      const data = await response.json();

      if (data.currentFlightNumber) {
        setCurrentFlightNumber(data.currentFlightNumber);
      }
      if (data.currentFlightDate) {
        setCurrentFlightDate(data.currentFlightDate);
      }

      const fullReply =
        data.reply || "I could not complete that request.";

      await typeReply(fullReply, (partial) => {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId
              ? { ...message, content: partial, streaming: true }
              : message
          )
        );
      });

      setMessages((prev) =>
        prev.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                content: fullReply,
                streaming: false,
              }
            : message
        )
      );
    } catch {
      const fallback =
        "Something went wrong while contacting the live airport feed. Please try again.";
      await typeReply(fallback, (partial) => {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId
              ? { ...message, content: partial, streaming: true }
              : message
          )
        );
      });
      setMessages((prev) =>
        prev.map((message) =>
          message.id === assistantId
            ? { ...message, content: fallback, streaming: false }
            : message
        )
      );
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void sendMessage(input);
  }

  return (
    <>
      <div className="sky" aria-hidden="true">
        <div className="sun" />
        <svg
          className="trail"
          viewBox="0 0 1440 900"
          preserveAspectRatio="none"
        >
          <path d="M-20 760 C 300 620, 380 380, 720 420 S 1200 160, 1460 120" />
        </svg>
        <div className="cloud c1" />
        <div className="cloud c2" />
        <div className="cloud c3" />
        <div className="cloud c4" />
      </div>

      <section className="chat" aria-label="Aviation AI chat">
        <div className="head">
          <div>
            <h1>Aviation AI</h1>
            <p>
              <span className="dot" aria-hidden="true" />
              Live at King Khalid International Airport
            </p>
          </div>
          {currentFlightNumber ? (
            <div className="pill">
              <PlaneIcon />
              Tracking {currentFlightNumber}
              {currentFlightDate ? ` · ${currentFlightDate}` : ""}
            </div>
          ) : (
            <div className="pill empty">No flight selected</div>
          )}
        </div>

        <div className="msgs">
          {messages.map((message) =>
            message.role === "user" ? (
              <div key={message.id} className="msg me">
                <div className="bubble">{message.content}</div>
              </div>
            ) : (
              <div key={message.id} className="msg bot">
                <div className="bubble">
                  {message.content}
                  {message.streaming ? (
                    <span className="caret" aria-hidden="true" />
                  ) : null}
                </div>
              </div>
            )
          )}

          {showWelcomeSuggestions ? (
            <div className="suggest">
              <small>Try a sample question</small>
              {SAMPLE_QUERIES.map((query) => (
                <button
                  key={query}
                  type="button"
                  onClick={() => void sendMessage(query)}
                  disabled={busy}
                >
                  <PlaneIcon />
                  {query}
                </button>
              ))}
            </div>
          ) : null}

          <div ref={endRef} />
        </div>

        <div className="quick" hidden={!currentFlightNumber || busy}>
          {QUICK_CHIPS.map((chip) => (
            <button
              key={chip}
              type="button"
              onClick={() => void sendMessage(chip)}
              disabled={busy}
            >
              {chip}
            </button>
          ))}
        </div>

        <form className="composer" onSubmit={onSubmit}>
          <label className="sr-only" htmlFor="passenger-question">
            Ask about your flight
          </label>
          <div className="field">
            <input
              id="passenger-question"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask about a flight number, gate, or terminal…"
              disabled={busy}
              autoComplete="off"
            />
          </div>
          <button
            className="send"
            type="submit"
            disabled={busy || !input.trim()}
            aria-label="Send message"
          >
            <PlaneIcon />
          </button>
        </form>

        <p className="foot">
          Live KKIA departures & arrivals · missing fields stay unavailable ·
          full LiquidAI tool-calling lives in the project notebook
        </p>
      </section>
    </>
  );
}
