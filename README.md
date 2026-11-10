# Aviation AI — Smart Airport Assistant

Live King Khalid International Airport (KKIA) flight lookup with LiquidAI/LFM2.5-1.2B-Instruct tool calling.

## Deliverables

1. **Python application** in `src/aviation_ai/`
2. **University notebook** `Aviation_AI_Project.ipynb` (Google Colab compatible)

## Quick start (local)

```bash
cd "/Users/janaalgurashi/Desktop/Aviation AI"
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Notebook (Colab or local)

Open `Aviation_AI_Project.ipynb` and run all cells in order.

- Prefers **CUDA** when available (Colab), then MPS, then CPU.
- Uses the public KKIA JSON feed (`/api/flightsInformation`).
- Does **not** invent flight data.
- Evaluation charts are generated from actual measured results.

## Web interface (LLM tool-calling)

The chat UI talks to the **LiquidAI LLM agent** (not hardcoded replies).

### Local (recommended — same LFM2.5-1.2B as the notebook)

Terminal 1 — start the agent API (loads the model once):

```bash
cd "/Users/janaalgurashi/Desktop/Aviation AI"
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src uvicorn aviation_ai.server:app --port 8000
```

Terminal 2 — start the web UI:

```bash
cd web
cp .env.example .env.local   # points at http://127.0.0.1:8000
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Replies come from `ask_agent` + `get_flight_info` tool calls.

### Deploy to Vercel

Vercel cannot host the local 1.2B PyTorch model. Use Liquid’s hosted API instead:

1. Create a key at [Liquid Console](https://docs.liquid.ai/api/overview).
2. In Vercel project env vars set:
   - `LIQUID_API_KEY=...`
   - `LIQUID_MODEL=lfm3-1.7b` (optional)
   - leave `USE_LOCAL_AGENT` unset
3. Set **Root Directory** to `web` and deploy.

The hosted path still uses real KKIA tool calling: the LLM decides when to call `get_flight_info`, then answers from the tool result.

## Lab concepts covered

| Lab | Concepts |
| --- | --- |
| Lab 1 | Tokenization, token analysis |
| Lab 2 | Retry, caching, streaming, TTFT |
| Lab 3 | Tool Schema, Pydantic, Registry, parallel tools, integration tests |
| Lab 6 | Conversation memory, fidelity gate |
| Lab 7 | Max steps, loop detection, tracing, evaluation |

RAG / embeddings / ChromaDB / UI are intentionally not implemented yet.
