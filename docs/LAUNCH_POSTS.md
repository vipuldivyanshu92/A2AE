# Launch posts — ready to copy/paste

Replace `<RAILWAY_URL>` and `<GITHUB_URL>` before posting.

---

## X / Twitter (280 chars, single post)

> Shipped Agent Escrow: open-source middleware so autonomous agents can pay each other safely for long-running work.
>
> - contract + funded hold + verifiable completion
> - AI Verification Engine audits the deliverable AND the full negotiation trace
> - runs on one Railway service
>
> <RAILWAY_URL>
> <GITHUB_URL>

### Thread variant (6 tweets)

1/ Agents are starting to delegate work to other agents. Two asymmetric risks:
— the requester pays and gets nothing verifiable.
— the doer works and never gets paid.
Agent Escrow is the smallest thing that makes this safe. Open source, MIT. 🧵

2/ The protocol is boring on purpose: CREATED → NEGOTIATED → FUNDED → IN_PROGRESS → SUBMITTED → VERIFIED → SETTLED (or REFUNDED). Every transition audited, every mutating call idempotent, scoped capability tokens on /start.

3/ Verification has two layers. A strict deterministic gate (JSON Schema on the deliverable) moves funds. On top, an AI Verification Engine audits the whole Alice↔Bob trace: state transitions, dispute-policy drift, deliverable-vs-contract consistency.

4/ The AI verifier has two backends — OpenAI when a key is set, deterministic heuristic otherwise. Same return shape. That's what made 30+ agent scale tests affordable without burning tokens. It's a pure auditor — never mutates state.

5/ HW8 scale: 30 → 60 → 120 real HTTP doer agents across parallel connection pools. Throughput plateaus at ~39 jobs/s — textbook single-writer-SQLite signature. Postgres is the next move. Zero HTTP errors in the sweep.

6/ Everything is one FastAPI process. Landing page + Swagger + API + HW7/HW8 experiment runners in a single Railway service. README has setup, curl demo, architecture, limitations.
Repo: <GITHUB_URL>
Demo: <RAILWAY_URL>

---

## LinkedIn

**Title:** Agent Escrow — shipping open-source infra so AI agents can pay each other safely

Autonomous agents are starting to delegate real work to other agents. The failure modes are simple and expensive: the requesting agent pays and gets nothing verifiable, or the doing agent works and never gets paid.

I've just open-sourced **Agent Escrow**, a minimal middleware that makes agent-to-agent work safe to buy and sell:

• Contract-first handshake between Alice (requester) and Bob (worker): output schema, budget, SLA, dispute policy.
• Funds are held in escrow before execution begins; scoped capability tokens gate /start.
• A deterministic verification gate decides release of funds — schema checks only; no LLM in the money-moving path.
• A new **AI Verification Engine** (OpenAI + deterministic-heuristic fallback) audits Bob's deliverable AND the full Alice↔Bob trace — state transitions, dispute-policy drift, contract consistency. It's a pure auditor; never mutates state.
• `GET /jobs/{id}/trace` returns the whole lifecycle (spec + contract + audit + deliverable) as a single JSON blob so external arbitrators can reason about it.
• Scale-tested with 30/60/120 real HTTP doer agents across independent connection pools; we measured throughput, p50/p95/p99 latency, and found the expected SQLite single-writer ceiling.

It ships as one FastAPI service: API + landing/docs site + experiment runners. One Railway click to deploy.

Live demo + docs: <RAILWAY_URL>
Repo (MIT): <GITHUB_URL>
Short white paper: <GITHUB_URL>/blob/main/docs/WHITEPAPER.md

If you're building agent marketplaces, arbitration agents, or multi-step workflows with payment, I'd love feedback. And if you want to plug your own framework (OpenClaw / LangGraph / Temporal) into the REST flow, it's a ~50-line adapter.

#AI #OpenSource #Agents #Infrastructure

---

## Reddit (r/LocalLLaMA, r/MachineLearning, r/OpenAI, r/programming)

**Title:** Open-sourced Agent Escrow — middleware so autonomous agents can pay each other safely (FastAPI, one Railway service, MIT)

I shipped an open-source escrow service for agent-to-agent work. It's boring on purpose: contract-first handshake, funded hold, scoped start tokens, deterministic verification, atomic settlement with a double-entry ledger, and full audit log.

On top, there's an **AI Verification Engine** with two entry points:

- `POST /jobs/{id}/verify_ai` — reviews the deliverable
- `POST /jobs/{id}/verify_trace` — audits the *entire* Alice↔Bob trace (spec → contract → audit log → deliverable → deterministic verdict) and flags policy drift / schema violations / missing transitions.

Dual backend (OpenAI or deterministic heuristic), so scale tests don't burn tokens. It's a pure auditor — never mutates state — which keeps it cleanly separable from the deterministic gate that moves funds.

Scale numbers (30/60/120 doer agents, multiple concurrent connection pools, 20% bad-deliverable injection): throughput plateaus at ~39 jobs/s on one node — textbook single-writer SQLite. Zero HTTP errors in the sweep. Postgres is the next step.

Everything is one FastAPI process: API + landing/docs site + experiment runners. One Railway service does it all.

Repo (MIT): <GITHUB_URL>
Live: <RAILWAY_URL>
Short write-up: <GITHUB_URL>/blob/main/docs/WHITEPAPER.md

Happy to take feedback, especially from people building arbitration agents or agent marketplaces.

---

## Hacker News (Show HN, one line + comment)

**Title:** Show HN: Agent Escrow – contract + verification for autonomous agents paying each other

**Text (optional body):**

Minimal middleware to make agent-to-agent work safe to buy and sell. Contract-first handshake, funded hold, scoped capability tokens, deterministic verification gate that moves funds, plus an AI Verification Engine that audits the whole Alice↔Bob trace (pure auditor, never mutates state). Dual backend — OpenAI with a deterministic heuristic fallback, so scale tests don't burn tokens. Scale-tested with 30/60/120 real HTTP doer agents; throughput plateaus at ~39 jobs/s on a single FastAPI + SQLite node (single-writer signature). One Railway service hosts the API, the landing page, and the Swagger docs. MIT.

Repo: <GITHUB_URL>
Demo: <RAILWAY_URL>
