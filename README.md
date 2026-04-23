# Agent Escrow

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Deploy on Railway](https://img.shields.io/badge/deploy-railway-5b2fff.svg)](https://railway.app)

**Middleware for safe, programmable agent-to-agent transactions.** A requester agent (Alice) posts a task with an output schema and budget; a worker agent (Bob) accepts terms; funds are held in escrow; Bob submits a deliverable + evidence; the system verifies and either settles or refunds. Includes a built-in **AI Verification Engine** that audits both Bob's deliverable *and* the full Alice&harr;Bob negotiation trace.

- **Live demo / docs:** your Railway URL (see [Deploy to Railway](#deploy-to-railway))
- **Interactive API explorer:** `/docs` on any running instance
- **API trace endpoint:** `GET /jobs/{id}/trace` returns the full lifecycle as a single JSON blob for external auditors

> Landing page you can host: open `/` on the running API — it's served by the same FastAPI process as a static site from `site/index.html`. So **one service on Railway = API + docs**.

---

## Table of contents

- [Why](#why)
- [Features](#features)
- [Architecture](#architecture)
- [Quick start (local)](#quick-start-local)
- [Deploy to Railway](#deploy-to-railway)
- [API reference](#api-reference)
- [AI Verification Engine](#ai-verification-engine)
- [Experiments (HW7 & HW8)](#experiments)
- [Configuration](#configuration)
- [Project layout](#project-layout)
- [Development](#development)
- [Limitations](#limitations)
- [License](#license)

---

## Why

Autonomous agents increasingly **delegate work to other agents** — research, browsing, code gen, data processing. For long-running tasks and uncertain outcomes:

- The **requesting agent** risks paying without a correct result.
- The **doer agent** risks working without getting paid.

Without an escrow primitive, agent marketplaces are fragile. Agent Escrow is the minimal safe coordination layer: structured intake, explicit handshake, funded hold, scoped execution, verifiable completion, atomic settlement, and an audit trail that any AI or human can later review.

## Features

- **Full lifecycle state machine** — `CREATED → NEGOTIATED → FUNDED → IN_PROGRESS → SUBMITTED → VERIFIED → SETTLED` (or `REFUNDED`).
- **Idempotency keys** on every state-mutating endpoint; safe to retry.
- **Double-entry ledger** (mocked PSP in v0; the adapter is the integration point).
- **Scoped capability tokens** (`/start` returns a job-scoped start token).
- **Deterministic verification** via JSON Schema-style gate on the deliverable.
- **AI Verification Engine** — `AIVerifier` reviews deliverables and full negotiation traces. OpenAI when a key is set, deterministic heuristic fallback otherwise.
- **`GET /jobs/{id}/trace`** — the complete Alice&harr;Bob trace (spec, contract, audit log, deliverable, evidence) in one read, for external auditors.
- **HW7 experiments** — five controlled suites (verification strictness, dispute policy, coordination/latency, failure recovery, LLM memory A/B).
- **HW8 scale runner** — ≥30 real HTTP doer agents across independent connection pools, with p50/p95/p99 latency and per-instance throughput.
- **Single-service deploy** — API + landing/docs site in one FastAPI process. One Railway service does everything.

## Architecture

```
Alice (requester)                                   Bob (worker)
      │                                                    │
      │ 1. POST /jobs                                      │
      │ 2. (await handshake)                               │
      │◀── 3. POST /jobs/{id}/handshake/accept ────────────│
      ▼                                                    ▼
┌────────────────────── Escrow API ───────────────────────┐
│                                                          │
│  Jobs      Contract     Ledger      Verification   Audit│
│  + state   + handshake  (double-    (deterministic +    │
│  machine   + policy      entry)      AI verifier)   log │
│                                                          │
│  SQLite / Postgres (via ESCROW_DATABASE_URL)             │
└──────────────────────────────────────────────────────────┘
      │                                                    │
      │ 4. /fund   5. /start   6. /submit                  │
      │ 7. /verify                                         │
      │ 8. /verify_ai | /verify_trace                      │
      │ 9. /settle or /refund                              │
```

Everything runs in one FastAPI process. The landing page (`site/index.html`) is served at `/`; Swagger at `/docs`; OpenAPI JSON at `/openapi.json`.

## Quick start (local)

Requires Python 3.12 (works on 3.11+).

```bash
git clone https://github.com/<you>/AgentEscrow.git
cd AgentEscrow
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Then:

- <http://localhost:8000/> — landing + docs
- <http://localhost:8000/docs> — interactive Swagger
- <http://localhost:8000/health> — liveness

Run a full lifecycle from the shell:

```bash
BASE=http://localhost:8000
JOB=$(curl -s -X POST $BASE/jobs \
  -H "Idempotency-Key: $(uuidgen)" -H "Content-Type: application/json" \
  -d '{"max_budget":"100","output_schema":{"type":"json-schema","definition":{"required":["result"]}},"task_description":"demo"}' \
  | jq -r .job_id)

curl -s -X POST $BASE/jobs/$JOB/handshake/accept \
  -H "Idempotency-Key: $(uuidgen)" -H "Content-Type: application/json" \
  -d '{"doer_id":"bob","dispute_policy":"refund"}'
curl -s -X POST $BASE/jobs/$JOB/fund  -H "Idempotency-Key: $(uuidgen)"
curl -s -X POST $BASE/jobs/$JOB/start
curl -s -X POST $BASE/jobs/$JOB/submit \
  -H "Idempotency-Key: $(uuidgen)" -H "Content-Type: application/json" \
  -d '{"deliverable":{"content":{"result":"done"},"mime_type":"application/json"},"evidence":[]}'
curl -s -X POST $BASE/jobs/$JOB/verify
curl -s -X POST $BASE/jobs/$JOB/settle -H "Idempotency-Key: $(uuidgen)"

# HW8: AI audit of the whole trace
curl -s -X POST $BASE/jobs/$JOB/verify_trace \
  -H "Content-Type: application/json" -d '{"backend":"auto"}' | jq
```

## Deploy to Railway

The repo is configured as a **single-service** deploy. Railway detects the `Dockerfile` and respects `railway.json` for healthchecks.

1. **Fork or import** this repository into your GitHub.
2. In Railway: **New Project → Deploy from GitHub Repo**, select your fork.
3. Railway will build with `Dockerfile` and start with the command from `railway.json`:
   ```
   uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
   ```
   Healthcheck is pinned to `/health`.
4. **(Recommended) Add a Volume** mounted at `/data` so the default SQLite DB (`sqlite:////data/escrow.db`) survives redeploys. In Railway: *Service → Settings → Volumes → Add Volume*, mount path `/data`.
5. **(Optional) Set environment variables** under *Service → Variables*:
   - `OPENAI_API_KEY` — enable real-LLM AI verifier and the HW7 exp5 memory-A/B experiment.
   - `OPENAI_VERIFIER_MODEL` — default `gpt-4o-mini`.
   - `ESCROW_CORS_ORIGINS` — comma-separated allowlist for browser clients (e.g. `https://your-ui.pages.dev`). Use `*` to allow any origin (disables credentials).
   - `ESCROW_DATABASE_URL` — override the DB (e.g. point at Railway's managed Postgres: `postgresql+psycopg2://...`).
6. **Deploy.** Railway assigns a public URL; the landing page is at `/`, API explorer at `/docs`.

### Upgrading to Postgres (recommended for production)

SQLite's single-writer lock is the main throughput ceiling (see [Limitations](#limitations)). To switch to Postgres on Railway:

1. Add a Postgres plugin to the project.
2. Copy the `DATABASE_URL` into `ESCROW_DATABASE_URL`, prefixing with the SQLAlchemy driver you want (e.g. `postgresql+psycopg2://...`). Install the driver in `requirements.txt` (`psycopg2-binary`).
3. Redeploy. Tables will be created on first request.

## API reference

Full OpenAPI spec at `/openapi.json`; interactive explorer at `/docs`.

| Method & path | Purpose | Notes |
|---|---|---|
| `POST /jobs` | Create job from task request | Requires `Idempotency-Key` header |
| `POST /jobs/{id}/handshake/accept` | Doer accepts terms | Supports `dispute_policy` |
| `POST /jobs/{id}/handshake/counteroffer` | Doer proposes new terms | Transitions to NEGOTIATED |
| `POST /jobs/{id}/fund` | Place escrow hold | Creates ledger entry |
| `POST /jobs/{id}/start` | Issue scoped start token | Only from FUNDED |
| `POST /jobs/{id}/submit` | Submit Completion Packet | Deliverable + evidence |
| `POST /jobs/{id}/verify` | Deterministic verification gate | Applies dispute policy on failure |
| `POST /jobs/{id}/settle` | Release funds | Idempotent, audited |
| `POST /jobs/{id}/refund` | Refund requester | Terminal |
| `GET  /jobs/{id}` | Current snapshot | Status, contract, doer |
| `GET  /jobs/{id}/trace` | **Full Alice↔Bob trace** | Spec + contract + audit + deliverable |
| `POST /jobs/{id}/verify_ai` | **AI review of the deliverable** | OpenAI or heuristic |
| `POST /jobs/{id}/verify_trace` | **AI audit of the entire lifecycle** | Returns verdict + deterministic snapshot |
| `POST /experiments/run` | Run HW7 suites 1–5 | Dashboard-friendly |
| `GET  /health` | Liveness | Railway healthcheck |

## AI Verification Engine

Two entry points, both in `src/escrow/ai_verification.AIVerifier`:

```python
verifier = AIVerifier(backend="auto")  # or "openai" | "heuristic"

verifier.review_deliverable(
    job_spec=spec, deliverable=deliverable, evidence=evidence,
)
# -> {"verdict": "accept"|"reject"|"needs_review", "score": 0..1,
#     "reasoning": str, "issues": [tag, ...], "backend": "...", "latency_s": ...}

verifier.review_negotiation_trace(
    job_spec=spec, contract=contract, audit_log=audit_log,
    deliverable=deliverable, evidence=evidence,
    deterministic_verification=det_verdict,
)
# -> same shape; checks state-transition completeness, dispute-policy drift,
#    and deliverable-vs-contract consistency.
```

**Dual backend:**

- **OpenAI** (default when `OPENAI_API_KEY` is set). Model = `OPENAI_VERIFIER_MODEL` (default `gpt-4o-mini`). Uses `response_format={"type": "json_object"}` and `temperature=0` for stable verdicts.
- **Heuristic** — deterministic Python rules. Same return shape. Used when no key is present, or when you pass `"backend": "heuristic"` to keep scale tests cheap (30+ LLM calls per run is expensive).

**Design principle:** the AI verifier is a *pure auditor*. It never mutates state. The deterministic `/verify` endpoint remains the only thing that can gate settlement; the AI verdict is audit evidence, which callers (arbitrators, bounty agents, humans) can act on separately.

## Experiments

### HW7 — controlled small-scale suites

Five suites in `experiments/run_agent_experiments.py`:

1. **Verification strictness** — strict vs loose `output_schema` on the same bad payload.
2. **Dispute policy fidelity** — handshake `dispute_policy` = refund vs arbitration, same failure.
3. **Coordination / latency** — sequential vs parallel six-lifecycle run.
4. **Failure recovery** — bad deliverable → verify fails → refund.
5. **LLM memory A/B** (requires `OPENAI_API_KEY`) — rich vs minimal system prompt; measures settle rate, tokens, rough USD.

Run from the CLI:

```bash
python experiments/run_agent_experiments.py --only all --trials 3
```

…or via the API:

```bash
curl -s -X POST http://localhost:8000/experiments/run \
  -H "Content-Type: application/json" \
  -d '{"only":"all","trials":3}' | jq
```

One-page results: `experiments/EXPERIMENT_SUMMARY.md`.

### HW8 — 30+ agents at scale

`experiments/scale_experiment.py` drives ≥30 real HTTP agents across N concurrent "cloud instance" simulators (each with its own `httpx.Client` + thread pool — the same code path as SSH-ing the runner to N cloud VMs).

```bash
python experiments/scale_experiment.py \
  --base http://localhost:8000 \
  --agents 30 --instances 3 \
  --bad-rate 0.2 \
  --ai-backend heuristic
```

Captured: outcomes (settled / refunded / verify_failed / http_error / exception), p50 / p95 / p99 / max lifecycle latency, AI-verifier latency, HTTP error breakdown, per-instance throughput. Reports land in `experiments/results/`.

One-page results: `experiments/EXPERIMENT_SUMMARY_HW8.md`. Video script: `experiments/VIDEO_ONE_MINUTE_SCRIPT_HW8.md`.

Sample sweep on a single FastAPI + SQLite node:

| Agents | Instances | Throughput | p50 | p95 | Errors |
|---:|---:|---:|---:|---:|---:|
| 30  | 3 | 38 jobs/s | 0.48 s | 0.72 s | 0 |
| 60  | 6 | 39 jobs/s | 1.01 s | 1.42 s | 0 |
| 120 | 8 | 39 jobs/s | 2.39 s | 2.89 s | 0 |

Throughput plateau + linear p50 growth = classic SQLite single-writer fingerprint. Move to Postgres for headroom.

## Configuration

All configuration is environment-variable based.

| Var | Default | Purpose |
|---|---|---|
| `ESCROW_DATABASE_URL` | `sqlite:///./escrow.db` (Docker: `sqlite:////data/escrow.db`) | SQLAlchemy URL |
| `ESCROW_CORS_ORIGINS` | *(empty)* | Extra CORS origins (comma-separated). `*` to allow any (disables credentials) |
| `OPENAI_API_KEY` | *(unset)* | Enables OpenAI-backed AI verifier and exp5 LLM agent |
| `OPENAI_VERIFIER_MODEL` | `gpt-4o-mini` | AI verifier model |
| `OPENAI_EXPERIMENT_MODEL` | `gpt-4o-mini` | HW7 exp5 model |
| `PORT` | `8000` | Railway sets this; Dockerfile honors it |

## Project layout

```
src/escrow/
  ai_verification.py       # HW8: AIVerifier (OpenAI + heuristic)
  api/
    jobs.py                # create, handshake, get
    fund.py start.py submit.py settle.py
    verification_ai.py     # HW8: /trace, /verify_ai, /verify_trace
    experiments_dashboard.py
    metrics_endpoint.py
  schemas/                 # job spec, contract, completion packet, ledger
  state.py                 # lifecycle state machine
  tokens.py verification.py ledger_service.py audit.py metrics.py repository.py
experiments/
  run_agent_experiments.py # HW7 suites 1–5
  scale_experiment.py      # HW8 scale runner (≥30 agents)
  llm_escrow_agent.py      # OpenAI-backed doer agent for exp5
  EXPERIMENT_SUMMARY.md
  EXPERIMENT_SUMMARY_HW8.md
  VIDEO_ONE_MINUTE_SCRIPT*.md
  CLOUD_RUNBOOK.md
docs/
  WHITEPAPER.md
  PEER_FEEDBACK_TEMPLATE.md
  LAUNCH_POSTS.md
site/
  index.html               # Landing + docs served at /
ui/                        # Optional React UI (local dev)
main.py                    # FastAPI app + static site mount
Dockerfile  Procfile  railway.json  requirements.txt
```

## Development

```bash
# API + reload
uvicorn main:app --reload --port 8000

# Frontend (optional)
cd ui && npm install && npm run dev

# Build the container locally
docker build -t agent-escrow .
docker run --rm -p 8000:8000 -e PORT=8000 agent-escrow

# Run all HW7 suites
python experiments/run_agent_experiments.py --only all --trials 3

# Run the HW8 scale sweep
python experiments/scale_experiment.py --agents 30 --instances 3
python experiments/scale_experiment.py --agents 120 --instances 8 --workers-per-instance 15
```

## Limitations

- **SQLite single-writer** is the throughput ceiling (~40 jobs/s in our HW8 measurements). Postgres + connection pooling is the first production move.
- **Payments are mocked.** The ledger records entries but there's no real PSP integration. The payments adapter is the integration point.
- **No authentication in v0.** Every mutating endpoint requires an `Idempotency-Key` header, but caller identity is trusted. Put this behind an API gateway / mTLS / OAuth for real deployments.
- **AI verifier is advisory only.** The deterministic `/verify` gate remains the only thing that moves funds; the AI verdict is audit evidence.
- **Hosted UI is not included** in the Railway deploy. The React UI in `ui/` is for local dev; hosting it is optional.
- **Callbacks/webhooks are not exercised at scale** in the current experiments (the protocol and the field are there, but there's no retry worker in v0).

## License

MIT — see [LICENSE](LICENSE).

---

*Built for the "AI for impact" course. HW7: controlled experiments. HW8: scale + AI verification engine. HW9: public release. See [`docs/WHITEPAPER.md`](docs/WHITEPAPER.md) for the architecture/research framing.*
