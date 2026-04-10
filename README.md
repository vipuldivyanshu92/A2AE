# Agentic Escrow Infrastructure

Middleware for safe, programmable agent-to-agent transactions. Enables escrow for long-running tasks with structured intake, doer handshake, payment hold, execution authorization, completion verification, and settlement.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn main:app --reload
```

API docs: http://localhost:8000/docs

## Web UI

Terminal 1: `uvicorn main:app --reload` (port 8000)

Terminal 2:

```bash
cd ui
npm install
npm run dev
```

Open http://localhost:5173 — the dev server proxies API calls to the backend. CORS is enabled for local Vite ports.

Use the **Agents** tab to register external identities (`doer_id`, optional webhook/base URLs) for your real runners (OpenClaw, cloud workers, etc.). **Workflow** can pick those doers and requester callbacks from the registry. **Experiments** can run with **six registered `doer_id` slots** (mapped across strict/loose/policy arms — see plan UI).

Use the **Experiments** tab for suites **1–5**: verification, policy, coordination/latency, **failure recovery (refund after failed verify)**, and optional **LLM memory A/B** (set `OPENAI_API_KEY` on the server, enable “Include LLM”). Use **Trials** for repeated runs and aggregate stats. See `experiments/CLOUD_RUNBOOK.md` and the `Dockerfile` for cloud deployment.

Production build: `cd ui && npm run build` — serve `ui/dist` with any static host and point `VITE_API_BASE` if the API is on another origin (see `ui/src/api.ts`).

## Flow

1. **Create job** `POST /jobs` (requires `Idempotency-Key`)
2. **Doer accepts** `POST /jobs/{id}/handshake/accept`
3. **Fund escrow** `POST /jobs/{id}/fund`
4. **Start execution** `POST /jobs/{id}/start` → returns start token
5. **Submit completion** `POST /jobs/{id}/submit`
6. **Verify** `POST /jobs/{id}/verify`
7. **Settle** `POST /jobs/{id}/settle`

## Project Structure

```
src/escrow/
  schemas/     # Job spec, contract, completion packet, ledger
  api/         # REST endpoints
  payments/    # Adapter (mocked for v0)
  state.py     # Lifecycle state machine
  tokens.py    # Start token generation
  verification.py
  ledger_service.py
  audit.py
  metrics.py
```
# A2AE
# A2AE
