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
