# Agent Escrow — Final Presentation Prompt

> **How to use this file:** Paste the entire contents below (everything from `BEGIN PROMPT` to `END PROMPT`) into Claude (or any LLM that can produce a `.pptx` / Google Slides spec) and ask it to generate the deck. Each `## Slide N` block is one slide. Speaker notes are in the `> Notes:` blocks. Replace the four bracketed links at the top before recording / submitting.

---

## Submission links (fill in)

- **GitHub repo:** https://github.com/vipuldivyanshu92/A2AE
- **Live deployed website:** https://<your-railway-app>.up.railway.app  *(landing at `/`, API at `/docs`, health at `/health`)*
- **1-minute demo video (YouTube, unlisted):** https://youtu.be/<id>
- **One-page experiment summaries (in repo):** [`experiments/EXPERIMENT_SUMMARY.md`](https://github.com/vipuldivyanshu92/A2AE/blob/main/experiments/EXPERIMENT_SUMMARY.md), [`experiments/EXPERIMENT_SUMMARY_HW8.md`](https://github.com/vipuldivyanshu92/A2AE/blob/main/experiments/EXPERIMENT_SUMMARY_HW8.md)

---

# ===== BEGIN PROMPT =====

You are a presentation designer. Generate a **10-slide deck** for the project below in PowerPoint-compatible format (also acceptable: Google Slides spec, Marp, or Reveal.js — pick one and produce a single file I can open).

**Style guide**

- Clean, modern, technical — Inter / IBM Plex Sans, dark text on white, single accent color `#5B2FFF` (the project's brand purple from the README badge).
- Each slide: 1 strong headline, 3–5 bullets max, 1 visual (diagram, table, or code snippet). No walls of text.
- Render the architecture (Slide 4) and the lifecycle state machine (Slide 5) as **diagrams**, not bullet lists. Use SmartArt / shapes — don't paste ASCII art into the slide body.
- Render Slide 7's results as a real table.
- Speaker notes should be added verbatim from the `Notes:` blocks under each slide. They should sound like a person talking, not a bulleted summary.
- Title slide should show the GitHub URL, deployed URL, and a QR code placeholder for the demo video.

**Project name:** Agent Escrow (A2AE) — *Middleware for safe, programmable agent-to-agent transactions*
**Author:** Vipul Divyanshu — AI for Impact, 2026
**Repo:** https://github.com/vipuldivyanshu92/A2AE
**License:** MIT

---

## Slide 1 — Title

**Headline:** Agent Escrow
**Subhead:** A safe-payment primitive for agent-to-agent work
**Visual:** Center the project logo / accent color block. Bottom strip: GitHub link · Live demo link · 1-min demo video QR.

> Notes: Hi — I'm presenting Agent Escrow, an open-source middleware that lets autonomous agents safely buy and sell work from each other. One requesting agent, one doing agent, funds held in the middle, an explicit contract, and a verifiable audit trail. I'll walk through the problem, why it's an agentic system, the architecture, what I actually built, what the experiments showed, what worked, what failed, and what I'd do next.

---

## Slide 2 — The problem

**Headline:** Agents are starting to delegate to other agents — and there's no safe-payment layer

**Bullets:**

- Autonomous agents now delegate research, code-gen, browsing, data jobs to other agents.
- The **requester** risks paying for a wrong / missing result.
- The **doer** risks doing the work and never getting paid.
- Human arbitration, prepaid marketplaces, and reputation don't compose with **long-running, machine-to-machine** tasks.
- What's missing: a small shared primitive agents can **call** — like a credit-card network — that holds funds, verifies completion, settles atomically, and emits an audit trail.

**Visual:** Two-agent diagram with a missing/broken arrow between them labeled "trust gap" and "$ ?".

> Notes: Today, if Alice asks Bob to do a research task, there is no shared piece of infrastructure that can guarantee Bob gets paid if he delivers and that Alice gets refunded if he doesn't. Humans solve this with credit cards, escrow agents, contracts. Agents have nothing equivalent. So agent marketplaces stall at toy demos. Agent Escrow is the smallest possible primitive that fixes that.

---

## Slide 3 — Why this is an agentic system

**Headline:** It's the coordination layer *between* agents — the agents are first-class users

**Bullets:**

- Both sides are **autonomous agents** driving REST endpoints; humans are not in the loop.
- A **JobSpec** carries machine-readable contract terms (output schema, SLA, budget, dispute policy) that agents reason over.
- An **AI Verification Engine** is a third agent that *audits* the trace (deliverable + Alice↔Bob negotiation) and produces verdicts.
- Capability tokens, idempotency keys, and callbacks are designed for **agent runtime** behavior (retries, parallelism, partial failure), not human UX.
- Outputs are signed audit bundles other agents (arbitrators, bounty hunters) can re-verify.

**Visual:** Three-agent triangle: Requester ↔ Worker, with an "AI Verifier" agent observing the channel.

> Notes: This is agentic in three concrete ways. First, the requester and the worker are both autonomous — every endpoint is designed for a machine caller. Second, the contract itself is an agent-readable artifact: the output schema is JSON-schema-like, the dispute policy is an enum, the SLA is a number. Agents can reason about it. Third, I built a separate AI verifier agent that audits both the deliverable and the full negotiation trace and emits its own verdict. So at minimum the system has three agents talking through it, and the design lets you slot in arbitrator agents and bounty agents on top.

---

## Slide 4 — System architecture

**Headline:** One FastAPI service, one DB, two integration seams

**Diagram (SmartArt — not bullets):**

- **Top row:** `Alice (requester agent)` — `Bob (worker agent)`
- **Center box ("Escrow API — single FastAPI process"):** five sub-modules side by side:
  1. *Jobs + State machine*
  2. *Contract / Handshake*
  3. *Double-entry Ledger*
  4. *Verification (deterministic + AI)*
  5. *Audit log + metrics*
- **Below:** `SQLite / Postgres` (toggle via `ESCROW_DATABASE_URL`)
- **Two outbound seams (dashed):** `Payments adapter` (mockable PSP) and `Callbacks / webhooks` (to requester agent).
- **Right side:** `AI Verification Engine` box with two backends — *OpenAI* and *Heuristic fallback*.

**Bullets (small, under diagram):**

- Single-service deploy on Railway: API + landing + Swagger from the same process.
- Two real integration points: payments (mocked PSP) and webhooks. Everything else is internal.

> Notes: The whole thing is one FastAPI process. The state machine, the ledger, the contract, the audit log, and the verification engine all live in the same service for v0 — that lets one Railway service do everything. The two clean seams to the outside world are the payments adapter, which today is a mock PSP but the interface is the integration point, and the callback / webhook system to notify the requester agent. The AI verifier is a separate component with two interchangeable backends so it works with or without an OpenAI key.

---

## Slide 5 — What I built

**Headline:** Full lifecycle state machine + contract + AI auditor

**Diagram (state machine, horizontal):**
`CREATED → NEGOTIATED → FUNDED → IN_PROGRESS → SUBMITTED → VERIFIED → SETTLED` with a branch from any failure into `REFUNDED`.

**Bullets:**

- 11 idempotent endpoints covering the full lifecycle (create → handshake → fund → start → submit → verify → settle / refund).
- **Scoped capability tokens** — `/start` issues a job-scoped, single-use token; funds cannot move without it.
- **Double-entry ledger** with idempotent `/settle` and `/refund`.
- **AI Verification Engine** — `POST /verify_ai` (deliverable) and `POST /verify_trace` (full Alice↔Bob audit). Pure auditor — never mutates state.
- **`GET /jobs/{id}/trace`** — single JSON blob with spec + contract + audit log + deliverable + evidence, for external auditors.
- Single-service Railway deploy, Docker, Postgres-ready (`ESCROW_DATABASE_URL`), CORS-configurable, OpenAPI at `/docs`.

> Notes: The deliverable is a working FastAPI service with the full lifecycle wired end-to-end. Every state-mutating endpoint is idempotent — you can retry it, which matters for agents. The deterministic verify step is the only thing that can gate settlement, but I added a separate AI verification engine that runs alongside it as a pure auditor. The trace endpoint is what makes the whole thing externally inspectable: any third agent can pull one URL and reason about whether the contract was honored.

---

## Slide 6 — Experiments: HW7 controlled (small-scale)

**Headline:** Five controlled suites, six labeled agents per wave — does the contract hold?

**Table:**

| # | Variable | Result |
|---|---|---|
| 1 | Strict vs loose `output_schema` | 6/6 expected outcomes — strict rejects, loose settles |
| 2 | Dispute policy at handshake (`refund` vs `arbitration`) | 6/6 — verify response `action` matches contract policy |
| 3 | Sequential vs parallel six-lifecycle run | Parallel slower locally (~0.8× speedup) — first signal of the SQLite write-lock bottleneck |
| 4 | Failure recovery — bad deliverable → refund | Reaches terminal `refunded` cleanly |
| 5 | LLM memory A/B (rich vs minimal prompt, real OpenAI) | Settle rate, tokens, USD captured per arm |

**Bullets:**

- Tightening the spec **flips outcomes** without changing the deliverable — the schema *is* the contract.
- The handshake's `dispute_policy` flows through verification — downstream automations can branch deterministically.
- Local parallel-vs-sequential surfaced an **architectural** finding, not a perf finding.

> Notes: HW7 was the controlled-variable round — six agents per experiment, isolated DB, vary one knob at a time. The two big wins: tightening the schema flips behavior predictably, which means the schema is acting as a real contract; and the dispute policy actually rides through to the verification response, so calling agents can branch on action without rereading the contract. The interesting failure was experiment 3 — parallel was slightly slower than sequential locally, which was the first hint that the server, not the client, was the bottleneck.

---

## Slide 7 — Experiments: HW8 scale + AI verifier

**Headline:** 30 / 60 / 120 real HTTP doer agents — what actually breaks

**Table (real measurements, 2026-04-22, FastAPI + SQLite, single node):**

| Agents | Instances | Wall | **Throughput** | p50 | p95 | p99 | HTTP errors |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 30  | 3 | 0.79 s | **38.1 j/s** | 0.48 s | 0.72 s | 0.73 s | 0 |
| 60  | 6 | 1.53 s | **39.1 j/s** | 1.01 s | 1.42 s | 1.48 s | 0 |
| 120 | 8 | 3.10 s | **38.7 j/s** | 2.39 s | 2.89 s | 2.93 s | 0 |

**Bullets:**

- Throughput **plateaus at ~39 jobs/s** regardless of client load → single-writer SQLite is the ceiling.
- p50 latency **scales linearly** with concurrency (0.48 → 1.0 → 2.4 s). Server is the bottleneck, not the network.
- 20% bad-deliverable injection — refund and settle paths contend on the same lock.
- AI verifier (heuristic backend) p95 inflates from 16 ms → 247 ms purely from server pressure on the same DB session.
- **Zero HTTP errors** at 120 agents — it queues, it doesn't crash.

> Notes: HW8 took the system past the demo. I drove 30, 60, and 120 real HTTP agents from multiple simulated cloud instances, each with its own connection pool, the same code path as running from N cloud VMs. Throughput is flat at about 39 jobs per second no matter how many agents I throw at it — that's the SQLite single-writer fingerprint. p50 latency doubles every time I double the agent count. No errors, just a longer queue. The system degrades gracefully, and the bottleneck is exactly where you'd expect it.

---

## Slide 8 — What worked

**Headline:** What actually held up under stress

**Bullets:**

- **Idempotency keys + state machine** — 30+ concurrent agents, retries, mixed good/bad deliverables, **zero double-pays, zero stuck states**.
- **Contract-first design** — the `dispute_policy` flowing through to the verify response means downstream agents need *one* read.
- **AI Verification Engine as pure auditor** — never mutates state, runs anytime, returns consistent verdicts. On a settled job: `{verdict: accept, score: 1.0}`. On a refund: `{verdict: needs_review, issues: ["deliverable:missing_required_field:result"]}` — exactly matching the deterministic gate's verdict.
- **Trace endpoint** — one JSON blob is enough for an external agent to audit a whole Alice↔Bob lifecycle.
- **Single-service deploy** — landing page, Swagger, API, health check, all in one Railway service.

> Notes: A few things that I'm genuinely happy with. The state machine plus idempotency keys held up cleanly through every scale run — no double-pays, no stuck jobs, even with 20% deliberate failures mixed in. The AI verifier and the deterministic gate produce consistent verdicts side by side, which is what made me trust the auditor design. And the trace endpoint turned out to be the right abstraction — one URL gives any external agent everything it needs.

---

## Slide 9 — What failed / what I learned

**Headline:** The scale runs surfaced things demos can't

**Bullets:**

- **SQLite single-writer is the ceiling** — every endpoint serializes through one write lock; client parallelism just lengthens the queue. *Fix: Postgres + connection pool, or at minimum SQLite WAL mode.*
- **Audit log had a real gap** — `JobRepository.create` inserts a `CREATED` row without an audit entry. The 30-agent run flagged `missing_state_transition:created` on every single trace. *Fixed in the trace reviewer; the deeper fix belongs in `create()`.*
- **Local parallel-vs-sequential in HW7 was a misleading signal** — I initially read it as "parallelism is slow." HW8 showed it was the write lock all along; I had to scale up to see it clearly.
- **AI verifier latency is coupled to server load**, not verifier work — even the cheap Python heuristic gets a 15× p95 inflation under load because it shares DB sessions with the lifecycle.
- **No real PSP, no auth in v0** — known scope cuts; the integration points are designed but not exercised.

> Notes: The honest part. The single biggest finding is that SQLite's write lock is the throughput ceiling — nothing else is close. I'd been suspicious of it since HW7 and HW8 confirmed it. The scale run also caught a real bug in my audit log accounting that no one-off demo could have caught: the very first state, CREATED, never has a `to_status` entry, so my heuristic was flagging every trace as missing the initial transition. That's the kind of bug you only see when you generate thirty traces at once. And v0 deliberately mocks the PSP and skips auth — the integration points are clean, but they're not real yet.

---

## Slide 10 — What I'd do next & demo

**Headline:** Where this goes from here

**Bullets:**

- **Postgres + connection pool** to break the ~39 j/s ceiling — wire is already there (`ESCROW_DATABASE_URL`).
- **Real PSP integration** behind the existing payments adapter (Stripe Connect or similar).
- **Authentication** — mTLS or API keys per agent, signed traces.
- **Arbitration & bounty agents** as third-party services consuming `GET /trace` — the protocol is designed for this.
- **Webhooks with retry worker** — protocol exists, retry loop doesn't yet.
- **Multi-step workflows** — chain escrow jobs so the deliverable of job A becomes the input of job B with audit continuity.

**Footer (links):**

- Live demo: `<railway-url>` (1-min walkthrough at `<youtube-url>`)
- Code: `github.com/vipuldivyanshu92/A2AE` · MIT
- One-page summaries: `experiments/EXPERIMENT_SUMMARY.md`, `experiments/EXPERIMENT_SUMMARY_HW8.md`

> Notes: Roadmap in priority order. Postgres is the obvious next move — the wiring is already there, only the deploy step changes. Real payments come next via the existing adapter seam. After that, the interesting agentic stuff: arbitration agents and bounty markets that consume the trace endpoint, multi-step workflows that chain escrow jobs into a single audit chain. Thanks — repo, live demo, and the one-minute video are all linked. Happy to take questions.

---

# ===== END PROMPT =====

---

## Appendix A — 1-minute demo video script (read while screen-recording)

> Record at 1080p with the live Railway URL open in one window and a terminal in the other. Total target: **~60 s**.

**0:00 – 0:08 — Hook.**
"Agent Escrow is open-source middleware that lets two autonomous agents safely transact. Alice posts a task, Bob accepts terms, funds are held, Bob delivers, the system verifies, and either settles or refunds — with a full audit trail."

**0:08 – 0:20 — Lifecycle in the terminal.**
*Run the curl block from the README — POST /jobs, /handshake/accept, /fund, /start, /submit, /verify, /settle.* Pause one second on the final settled response.
"Seven endpoints, all idempotent, full lifecycle in under a second locally."

**0:20 – 0:32 — AI Verification Engine.**
*Run `curl -s -X POST $BASE/jobs/$JOB/verify_trace -d '{"backend":"auto"}' | jq`.* Highlight `verdict: accept`, `score: 1.0`, `deterministic_snapshot.verified: true`.
"A separate AI verifier audits the whole Alice-to-Bob trace — spec, contract, audit log, deliverable. Returns `accept` on a clean job, `needs_review` with the exact failing field on a bad one. Pure auditor — never mutates state."

**0:32 – 0:48 — Scale results (cut to the table).**
"I ran 30, 60, and 120 real HTTP doer agents against this. Throughput flatlined at 39 jobs per second — that's the SQLite single-writer fingerprint. Zero HTTP errors at 120 agents, p50 latency scales linearly. Server's the bottleneck, not the agents — Postgres is the next move."

**0:48 – 1:00 — What this enables.**
"Once agents can commit to each other's work, you get real agent marketplaces, arbitration agents that consume the trace endpoint, and bounty markets on the dispute policy. Code's MIT, one-line Railway deploy. Repo and live demo are in the description."

---

## Appendix B — Backup demo (if live deploy is down)

If Railway is rate-limited / cold / down at presentation time:

```bash
git clone https://github.com/vipuldivyanshu92/A2AE.git
cd A2AE
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload &
# then run the 7-step curl block from README.md
python experiments/scale_experiment.py --base https://a2ae-production.up.railway.app --agents 30 --instances 3 --bad-rate 0.2 --ai-backend heuristic
```

The fallback gives the same ~38 jobs/s number on a laptop and the same AI-verifier output as the live deploy.
