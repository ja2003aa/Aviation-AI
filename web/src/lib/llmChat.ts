import {
  FlightLookupResult,
  FlightRecord,
  getFlightInfo,
  humanStatus,
} from "@/lib/flights";

export type LlmChatResult = {
  reply: string;
  usedTool: boolean;
  currentFlightNumber: string | null;
  currentFlightDate: string | null;
  toolResult: {
    found?: boolean;
    message?: string;
    flight: FlightRecord | null;
    retrieved_at_utc?: string;
    source?: string;
  } | null;
  source: "local-agent" | "liquid-api";
};

const FLIGHT_TOOL = {
  type: "function" as const,
  function: {
    name: "get_flight_info",
    description:
      "Look up live KKIA flight info by flight number. Use for status, gate, terminal, time, arrival, or departure. Do not invent data.",
    parameters: {
      type: "object",
      properties: {
        flight_number: {
          type: "string",
          description: "Flight number like SV1096 or XY790",
        },
        flight_date: {
          type: "string",
          description: "Optional date YYYY-MM-DD",
        },
      },
      required: ["flight_number"],
    },
  },
};

const SYSTEM_PROMPT = `You are Aviation AI for King Khalid International Airport (Riyadh / RUH).

Rules:
1. If the passenger mentions a flight number, call get_flight_info.
2. If they ask about "its" gate/terminal/status and a flight was already discussed, call get_flight_info for that flight.
3. If there is no flight number and no prior flight context, reply: Please share your flight number (like SV1096) and I will look up the live information.
4. Answer the passenger's specific question in one short plain sentence.
5. Never invent flight details. Use ONLY tool results.
6. Translate status codes into plain language (OT = on time, DL = delayed, CX = cancelled). Never say "status code" or raw codes like OT.
7. If flight_status / status_label is unavailable, say: Flight status is currently unavailable.
8. Keep status, gate, terminal, and scheduled time separate — do not mix them.`;

function enrichForLlm(result: FlightLookupResult): Record<string, unknown> {
  const flights = result.flights.map((flight) => ({
    ...flight,
    status_label: humanStatus(flight.flight_status),
    flight_status: humanStatus(flight.flight_status) || flight.flight_status,
  }));
  return {
    found: result.found,
    message: result.message,
    flights,
    retrieved_at_utc: result.retrieved_at_utc,
    source: result.source,
  };
}

type ChatMessage = {
  role: "system" | "user" | "assistant" | "tool";
  content: string | null;
  tool_calls?: Array<{
    id: string;
    type: "function";
    function: { name: string; arguments: string };
  }>;
  tool_call_id?: string;
  name?: string;
};

async function liquidChatCompletions(
  messages: ChatMessage[],
  apiKey: string,
  model: string
): Promise<ChatMessage> {
  const response = await fetch("https://api.liquid.ai/openai/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model,
      messages,
      tools: [FLIGHT_TOOL],
      tool_choice: "auto",
      temperature: 0.1,
      top_k: 50,
      repetition_penalty: 1.05,
    }),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Liquid API error (${response.status}): ${detail.slice(0, 300)}`);
  }

  const data = await response.json();
  const message = data.choices?.[0]?.message;
  if (!message) {
    throw new Error("Liquid API returned an empty response.");
  }
  return message as ChatMessage;
}

function assistantText(message: ChatMessage & { reasoning_content?: string }): string {
  const content = (message.content || "").trim();
  if (content) return content;
  return "";
}

/** Hosted Liquid AI API with OpenAI-style tool calling (works on Vercel). */
export async function chatWithLiquidApi(options: {
  message: string;
  currentFlightNumber?: string | null;
  currentFlightDate?: string | null;
}): Promise<LlmChatResult> {
  const apiKey = (process.env.LIQUID_API_KEY || "").trim();
  if (!apiKey) {
    throw new Error(
      "LIQUID_API_KEY is missing. In Vercel: Settings → Environment Variables → add LIQUID_API_KEY, then Redeploy."
    );
  }
  const model = (process.env.LIQUID_MODEL || "lfm3-1.7b").trim();

  let contextHint = "";
  if (options.currentFlightNumber) {
    contextHint = `\n\n[Prior context: tracking flight ${options.currentFlightNumber}${
      options.currentFlightDate ? ` on ${options.currentFlightDate}` : ""
    }. Use this for follow-ups like "its gate".]`;
  }

  const messages: ChatMessage[] = [
    { role: "system", content: SYSTEM_PROMPT },
    { role: "user", content: `${options.message}${contextHint}` },
  ];

  let usedTool = false;
  let lastLookup: FlightLookupResult | null = null;
  let currentFlightNumber = options.currentFlightNumber || null;
  let currentFlightDate = options.currentFlightDate || null;

  for (let step = 0; step < 3; step += 1) {
    const assistant = await liquidChatCompletions(messages, apiKey, model);
    messages.push(assistant);

    const toolCalls = assistant.tool_calls || [];
    if (toolCalls.length === 0) {
      return {
        reply: assistantText(assistant) || "I could not complete that request.",
        usedTool,
        currentFlightNumber,
        currentFlightDate,
        toolResult: lastLookup
          ? {
              found: lastLookup.found,
              message: lastLookup.message,
              flight: lastLookup.flights[0] || null,
              retrieved_at_utc: lastLookup.retrieved_at_utc,
              source: lastLookup.source,
            }
          : null,
        source: "liquid-api",
      };
    }

    usedTool = true;
    for (const call of toolCalls) {
      let args: { flight_number?: string; flight_date?: string } = {};
      try {
        args = JSON.parse(call.function.arguments || "{}");
      } catch {
        args = {};
      }
      const flightNumber =
        args.flight_number || currentFlightNumber || undefined;
      const flightDate = args.flight_date || currentFlightDate || null;

      if (!flightNumber) {
        messages.push({
          role: "tool",
          tool_call_id: call.id,
          content: JSON.stringify({
            found: false,
            message: "No flight number provided.",
            flights: [],
          }),
        });
        continue;
      }

      try {
        lastLookup = await getFlightInfo(flightNumber, flightDate);
        currentFlightNumber = flightNumber;
        currentFlightDate =
          flightDate ||
          (lastLookup.flights[0]?.scheduled_time || "").slice(0, 10) ||
          currentFlightDate;

        messages.push({
          role: "tool",
          tool_call_id: call.id,
          content: JSON.stringify(enrichForLlm(lastLookup)),
        });
      } catch (toolError) {
        const detail =
          toolError instanceof Error ? toolError.message : "Flight lookup failed";
        messages.push({
          role: "tool",
          tool_call_id: call.id,
          content: JSON.stringify({
            found: false,
            message: `Live airport feed error: ${detail}`,
            flights: [],
          }),
        });
      }
    }
  }

  return {
    reply: "Stopped safely after too many tool steps. Please ask again.",
    usedTool,
    currentFlightNumber,
    currentFlightDate,
    toolResult: lastLookup
      ? {
          found: lastLookup.found,
          message: lastLookup.message,
          flight: lastLookup.flights[0] || null,
          retrieved_at_utc: lastLookup.retrieved_at_utc,
          source: lastLookup.source,
        }
      : null,
    source: "liquid-api",
  };
}

/** Local Python FastAPI wrapping LFM2.5-1.2B ask_agent (the project model). */
export async function chatWithLocalAgent(options: {
  message: string;
  sessionId: string;
}): Promise<LlmChatResult> {
  const base = (process.env.AVIATION_AGENT_URL || "http://127.0.0.1:8000").replace(
    /\/$/,
    ""
  );

  const response = await fetch(`${base}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: options.message,
      session_id: options.sessionId,
    }),
    // Local model can be slow on CPU/MPS.
    signal: AbortSignal.timeout(180_000),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Local agent error (${response.status}): ${detail.slice(0, 300)}`);
  }

  const data = await response.json();
  const flight = data.tool_result?.flight || null;

  return {
    reply: data.reply,
    usedTool: Boolean(data.used_tool),
    currentFlightNumber: flight?.flight_number || null,
    currentFlightDate: (flight?.scheduled_time || "").slice(0, 10) || null,
    toolResult: data.tool_result || null,
    source: "local-agent",
  };
}

export function llmMode(): "local-agent" | "liquid-api" | "none" {
  // Vercel / hosted path: LIQUID_API_KEY wins unless local agent is forced on.
  if (process.env.LIQUID_API_KEY && process.env.USE_LOCAL_AGENT !== "1") {
    return "liquid-api";
  }
  if (process.env.USE_LOCAL_AGENT === "1" || process.env.AVIATION_AGENT_URL) {
    return "local-agent";
  }
  if (process.env.LIQUID_API_KEY) {
    return "liquid-api";
  }
  return "none";
}
