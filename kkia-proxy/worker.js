/**
 * Tiny Cloudflare Worker — proxies KKIA flights JSON for Vercel.
 * Deploy: cd kkia-proxy && npx wrangler deploy
 */
export default {
  async fetch() {
    const upstream = await fetch(
      "https://www.kkia.sa/api/flightsInformation",
      {
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
          Accept: "application/json",
          "Accept-Language": "en-US,en;q=0.9",
          Referer: "https://www.kkia.sa/en/Flights/Departures-and-Arrivals",
          Origin: "https://www.kkia.sa",
          Cookie: "sc_site=KKIA",
        },
      }
    );

    const body = await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: {
        "content-type":
          upstream.headers.get("content-type") || "application/json",
        "access-control-allow-origin": "*",
        "cache-control": "public, max-age=30",
      },
    });
  },
};
