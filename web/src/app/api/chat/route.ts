import { NextRequest, NextResponse } from "next/server";
import { seedBoardFromPayload } from "@/lib/flights";
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
  /** Raw KKIA JSON array fetched in the browser (avoids Vercel IP 403). */
  boardPayload?: unknown;
};

export const maxDuration = 60;

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as ChatBody;
    const message = (body.message || "").trim();
    if (!message) {
      return NextResponse.json({ error: "Please enter a message." }, { status: 400 });
    }

    const sessionId = body.sessionId || "web";
    const mode = llmMode();

    if (body.boardPayload != null) {
      seedBoardFromPayload(body.boardPayload);
    }

    if (mode === "none") {
      return NextResponse.json(
        {
          reply:
            "No LLM configured on this deployment. In Vercel → Settings → Environment Variables add LIQUID_API_KEY, LIQUID_MODEL=lfm3-1.7b, USE_LOCAL_AGENT=0 (Production + Preview), then Redeploy.",
          usedTool: false,
          toolResult: null,
          source: "none",
          mode,
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
        mode,
      });
    } catch (agentError) {
      const detail =
        agentError instanceof Error ? agentError.message : "Unknown agent error";
      const hint =
        mode === "liquid-api"
          ? "Fix in Vercel → Settings → Environment Variables (LIQUID_API_KEY, LIQUID_MODEL=lfm3-1.7b, USE_LOCAL_AGENT=0), then Redeploy."
          : "Local agent is offline. Start ./run_agent_api.sh or switch to LIQUID_API_KEY.";

      return NextResponse.json(
        {
          reply: `The LLM agent failed. ${hint}\n\nDetails: ${detail}`,
          usedTool: false,
          error: detail,
          toolResult: null,
          source: "none",
          mode,
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
