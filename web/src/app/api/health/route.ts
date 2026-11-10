import { NextResponse } from "next/server";
import { fetchBoard } from "@/lib/flights";
import { llmMode } from "@/lib/llmChat";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

/** Safe diagnostics for Vercel — never returns the API key. */
export async function GET() {
  const key = (process.env.LIQUID_API_KEY || "").trim();
  const model = (process.env.LIQUID_MODEL || "").trim() || null;
  const useLocal = process.env.USE_LOCAL_AGENT ?? null;
  const mode = llmMode();

  let liquidOk: boolean | null = null;
  let liquidError: string | null = null;
  if (key) {
    try {
      const response = await fetch("https://api.liquid.ai/openai/v1/models", {
        headers: { Authorization: `Bearer ${key}` },
        cache: "no-store",
      });
      liquidOk = response.ok;
      if (!response.ok) {
        liquidError = `Liquid models HTTP ${response.status}`;
      }
    } catch (error) {
      liquidOk = false;
      liquidError = error instanceof Error ? error.message : "Liquid fetch failed";
    }
  }

  let kkiaOk: boolean | null = null;
  let kkiaCount: number | null = null;
  let kkiaError: string | null = null;
  try {
    const board = await fetchBoard();
    kkiaOk = true;
    kkiaCount = board.flights.length;
  } catch (error) {
    kkiaOk = false;
    kkiaError = error instanceof Error ? error.message : "KKIA fetch failed";
  }

  return NextResponse.json({
    ok: Boolean(key) && liquidOk === true && kkiaOk === true,
    mode,
    env: {
      hasLiquidApiKey: Boolean(key),
      liquidKeyLength: key.length,
      liquidModel: model,
      useLocalAgent: useLocal,
    },
    liquidOk,
    liquidError,
    kkiaOk,
    kkiaCount,
    kkiaError,
  });
}
