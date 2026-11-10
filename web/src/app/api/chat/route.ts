import { NextRequest, NextResponse } from "next/server";
import {
  chatWithLiquidApi,
  chatWithLocalAgent,
  llmMode,
} from "@/lib/llmChat";

type ChatBody = {
  message?: string;
  sessionId?: string;
  currentFlightNumber?: string | null;
  currentFlightDate?: string | null;
};

export const maxDuration = 180;

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as ChatBody;
    const message = (body.message || "").trim();
    if (!message) {
      return NextResponse.json({ error: "Please enter a message." }, { status: 400 });
    }

    const sessionId = body.sessionId || "web";
    const mode = llmMode();

    if (mode === "none") {
      return NextResponse.json(
        {
          reply:
            "No LLM configured. For the Vercel path, set LIQUID_API_KEY in web/.env.local (and USE_LOCAL_AGENT=0). For local LFM2.5, set USE_LOCAL_AGENT=1 and start ./run_agent_api.sh.",
          usedTool: false,
          toolResult: null,
          source: "none",
        },
        { status: 503 }
      );
    }

    try {
      const result =
        mode === "liquid-api"
          ? await chatWithLiquidApi({
              message,
              currentFlightNumber: body.currentFlightNumber,
              currentFlightDate: body.currentFlightDate,
            })
          : await chatWithLocalAgent({ message, sessionId });

      return NextResponse.json({
        reply: result.reply,
        usedTool: result.usedTool,
        currentFlightNumber:
          result.currentFlightNumber || body.currentFlightNumber || null,
        currentFlightDate:
          result.currentFlightDate || body.currentFlightDate || null,
        toolResult: result.toolResult,
        source: result.source,
      });
    } catch (agentError) {
      const detail =
        agentError instanceof Error ? agentError.message : "Unknown agent error";
      const hint =
        mode === "liquid-api"
          ? "Check LIQUID_API_KEY / LIQUID_MODEL in web/.env.local."
          : "Start the LFM agent: `./run_agent_api.sh`. Or set LIQUID_API_KEY for hosted Liquid tool-calling.";

      return NextResponse.json(
        {
          reply: `The LLM agent is not reachable yet. ${hint}`,
          usedTool: false,
          error: detail,
          toolResult: null,
          source: "none",
        },
        { status: 503 }
      );
    }
  } catch (error) {
    const detail = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      {
        reply: "Something went wrong while talking to the LLM agent.",
        usedTool: false,
        error: detail,
        toolResult: null,
      },
      { status: 500 }
    );
  }
}
