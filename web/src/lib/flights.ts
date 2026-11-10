export type FlightRecord = {
  flight_number: string | null;
  airline: string | null;
  direction: string | null;
  origin: string | null;
  destination: string | null;
  scheduled_time: string | null;
  terminal: string | null;
  gate: string | null;
  flight_status: string | null;
};

export type FlightLookupResult = {
  found: boolean;
  message: string;
  flights: FlightRecord[];
  retrieved_at_utc: string;
  source: string;
};

const FLIGHTS_API = "https://www.kkia.sa/api/flightsInformation";
const PAGE_URL = "https://www.kkia.sa/en/Flights/Departures-and-Arrivals";

let cachedPayload: unknown[] | null = null;
let cachedAt = 0;
const CACHE_MS = 60_000;

export function normalizeFlightNumber(value: string): string {
  return value.toUpperCase().replace(/[\s\-_]+/g, "");
}

function show(value: string | null | undefined): string | null {
  if (value == null || value === "") return null;
  return value;
}

function place(airport: Record<string, unknown> | null | undefined): string | null {
  if (!airport) return null;
  const code = String(airport.code || "").trim();
  const description = String(airport.description || airport.name || "").trim();
  if (code && description) return `${description} (${code})`;
  return description || code || null;
}

export function parseFlight(item: Record<string, unknown>): FlightRecord {
  const extras = item.flightExtraData;
  const extra =
    Array.isArray(extras) && extras[0] && typeof extras[0] === "object"
      ? (extras[0] as Record<string, unknown>)
      : {};
  const airline =
    item.airline && typeof item.airline === "object"
      ? (item.airline as Record<string, unknown>)
      : {};

  const code = String(extra.airlineCode || airline.code || "").trim();
  const number = String(item.number || "").trim();
  const suffix = String(item.flightNumberSuffix || "").trim();
  const status = (extra.flightStatus ||
    extra.flightState ||
    item.remark ||
    null) as string | null;
  const gate = (item.passengerGate || extra.passengerGate || null) as
    | string
    | null;
  const terminal = (item.aircraftTerminal ||
    extra.publicTerminal ||
    null) as string | null;

  return {
    flight_number: code || number ? `${code}${number}${suffix}` : null,
    airline: show(
      String(extra.airlineDescription || airline.description || "") || null
    ),
    direction: show(String(item.departureOrArrival || "") || null),
    origin: place(item.departureAirport as Record<string, unknown>),
    destination: place(item.arrivalAirport as Record<string, unknown>),
    scheduled_time: show(String(item.scheduled || "") || null),
    terminal: show(terminal),
    gate: show(gate),
    flight_status: show(status),
  };
}

export async function fetchBoard(): Promise<{
  flights: FlightRecord[];
  retrieved_at_utc: string;
}> {
  const now = Date.now();
  if (cachedPayload && now - cachedAt < CACHE_MS) {
    return {
      flights: (cachedPayload as Record<string, unknown>[]).map(parseFlight),
      retrieved_at_utc: new Date(cachedAt).toISOString(),
    };
  }

  const response = await fetch(FLIGHTS_API, {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (compatible; AviationAI/1.0; +https://github.com/ja2003aa/Aviation-AI)",
      Accept: "application/json,text/plain,*/*",
      Referer: PAGE_URL,
      Origin: "https://www.kkia.sa",
    },
    // Always hit live board from serverless — do not use Next data cache.
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`KKIA feed unavailable (${response.status})`);
  }

  const payload = await response.json();
  if (!Array.isArray(payload)) {
    throw new Error("Unexpected KKIA payload");
  }

  cachedPayload = payload;
  cachedAt = now;
  return {
    flights: payload.map((item) => parseFlight(item as Record<string, unknown>)),
    retrieved_at_utc: new Date(cachedAt).toISOString(),
  };
}

export async function getFlightInfo(
  flightNumber: string,
  flightDate?: string | null
): Promise<FlightLookupResult> {
  const board = await fetchBoard();
  const needle = normalizeFlightNumber(flightNumber);
  const dateFilter = flightDate?.trim() || null;

  const matches = board.flights.filter((flight) => {
    if (!flight.flight_number) return false;
    if (normalizeFlightNumber(flight.flight_number) !== needle) return false;
    if (dateFilter && !String(flight.scheduled_time || "").startsWith(dateFilter)) {
      return false;
    }
    return true;
  });

  return {
    found: matches.length > 0,
    message: matches.length
      ? `Found ${matches.length} matching flight(s).`
      : "This flight is unavailable in the current airport feed.",
    flights: matches,
    retrieved_at_utc: board.retrieved_at_utc,
    source: PAGE_URL,
  };
}

export function extractFlightQuery(text: string): {
  flightNumber: string | null;
  flightDate: string | null;
} {
  const flightMatch = text.match(/\b([A-Za-z]{2,3}\s?-?\s?\d{1,4}[A-Za-z]?)\b/);
  const dateMatch = text.match(/\b(\d{4}-\d{2}-\d{2})\b/);
  return {
    flightNumber: flightMatch
      ? normalizeFlightNumber(flightMatch[1])
      : null,
    flightDate: dateMatch ? dateMatch[1] : null,
  };
}

/** Turn airport status codes into plain language passengers understand. */
export function humanStatus(code: string | null | undefined): string | null {
  if (code == null || code === "" || code === "<not available>") return null;
  const raw = code.trim();
  const s = raw.toUpperCase();

  const exact: Record<string, string> = {
    OT: "on time",
    ON: "on time",
    "ON TIME": "on time",
    DL: "delayed",
    DELAY: "delayed",
    DELAYED: "delayed",
    ES: "delayed",
    CX: "cancelled",
    CANCEL: "cancelled",
    CANCELLED: "cancelled",
    CANCELED: "cancelled",
    LD: "landed",
    LANDED: "landed",
    ARR: "arrived",
    ARRIVED: "arrived",
    DP: "departed",
    DEP: "departed",
    DEPARTED: "departed",
    BD: "boarding",
    BOARDING: "boarding",
    GC: "gate closed",
    DV: "diverted",
    DIVERTED: "diverted",
    FR: "in flight",
    AIRBORNE: "in flight",
  };

  if (exact[s]) return exact[s];
  if (s.includes("CANCEL")) return "cancelled";
  if (s.includes("DELAY") || s === "ES") return "delayed";
  if (s.includes("BOARD")) return "boarding";
  if (s.includes("LAND")) return "landed";
  if (s.includes("DEPART")) return "departed";
  if (s.includes("ARRIV")) return "arrived";
  if (s.includes("DIVERT")) return "diverted";
  if (s.includes("ON TIME") || s === "OT") return "on time";
  // Already a readable phrase — keep it, never echo cryptic codes alone.
  if (/[a-z]/.test(raw) || raw.includes(" ")) return raw.toLowerCase();
  return raw;
}

export function answerFromTool(
  question: string,
  result: FlightLookupResult
): string {
  const q = question.toLowerCase();

  if (!result.found || result.flights.length === 0) {
    return "This flight is unavailable in the current airport feed.";
  }

  const flight = result.flights[0];
  const unavailable = (value: string | null) =>
    value == null || value === "" || value === "<not available>";
  const statusLabel = humanStatus(flight.flight_status);

  if (q.includes("status") || q.includes("delayed")) {
    if (!statusLabel) {
      return "Flight status is currently unavailable.";
    }
    if (q.includes("delayed")) {
      const delayed = statusLabel === "delayed";
      return delayed
        ? `Yes — flight ${flight.flight_number} is delayed.`
        : `No — flight ${flight.flight_number} is ${statusLabel}.`;
    }
    return `Flight ${flight.flight_number} is ${statusLabel}.`;
  }

  if (q.includes("gate")) {
    if (unavailable(flight.gate)) {
      return `Gate information for flight ${flight.flight_number} is currently unavailable.`;
    }
    return `Flight ${flight.flight_number} is at gate ${flight.gate}.`;
  }

  if (q.includes("terminal")) {
    if (unavailable(flight.terminal)) {
      return `Terminal information for flight ${flight.flight_number} is currently unavailable.`;
    }
    return `Flight ${flight.flight_number} is at terminal ${flight.terminal}.`;
  }

  const parts = [
    `Flight ${flight.flight_number}`,
    flight.airline ? `(${flight.airline})` : null,
    flight.direction ? `is an ${flight.direction.toLowerCase()}` : null,
    flight.origin && flight.destination
      ? `from ${flight.origin} to ${flight.destination}`
      : null,
    flight.scheduled_time ? `scheduled at ${flight.scheduled_time}` : null,
    flight.terminal ? `terminal ${flight.terminal}` : null,
  ].filter(Boolean);

  let answer = parts.join(" ") + ".";
  if (unavailable(flight.gate)) {
    answer += " Gate is currently unavailable.";
  }
  if (!statusLabel) {
    answer += " Flight status is currently unavailable.";
  } else {
    answer += ` It is currently ${statusLabel}.`;
  }
  return answer;
}
