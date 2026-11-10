/** Browser-side KKIA board fetch (works where Vercel server IPs get 403). */

const FLIGHTS_API = "https://www.kkia.sa/api/flightsInformation";

let cached: unknown[] | null = null;
let cachedAt = 0;
const CACHE_MS = 60_000;

export async function fetchBoardInBrowser(): Promise<unknown[] | null> {
  const now = Date.now();
  if (cached && now - cachedAt < CACHE_MS) {
    return cached;
  }

  try {
    const response = await fetch(FLIGHTS_API, {
      method: "GET",
      headers: { Accept: "application/json" },
      mode: "cors",
      cache: "no-store",
    });
    if (!response.ok) return cached;
    const payload = await response.json();
    if (!Array.isArray(payload)) return cached;
    cached = payload;
    cachedAt = now;
    return payload;
  } catch {
    return cached;
  }
}
