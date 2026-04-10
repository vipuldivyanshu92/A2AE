# Agent Escrow — Small-Scale Agent Experiments (1 page)

**Goal:** Treat the MVP escrow API as a system under test: vary contract/verification/coordination knobs, record expected vs observed behavior, and run **six distinct doer agent identities** per experiment wave (HTTP clients labeled per “instance”; same pattern works for OpenClaw or any tool-calling agent that hits REST).

**Setup:** Escrow API (FastAPI) backed by SQLite for isolation (`ESCROW_DATABASE_URL`). Clients use `experiments/run_agent_experiments.py` with `ESCROW_API_BASE` and `INSTANCE_LABEL` (set per cloud VM so traces read as `doer-<label>-…`). **Cloud replication:** deploy the API to one host; from **≥2 other instances** run the same script against that base URL with different `INSTANCE_LABEL` values so logs and `doer_id` values reflect distributed runners (6+ logical agents across instances and trials).

---

## What we tested

| # | Focus | Independent variable | Held constant |
|---|--------|----------------------|---------------|
| **1** | Verification / “memory” of spec | **Strict vs loose `output_schema`** (required key `result` vs none) | Same malformed deliverable `{"answer": …}` |
| **2** | Tool / policy contract | **`dispute_policy` at handshake** (`refund` vs `arbitration`) | Same deterministic verification failure |
| **3** | Coordination & latency | **Sequential vs parallel** execution of six full lifecycles | Same happy-path payload and settle |

---

## What we changed (between arms)

1. **Job spec:** `output_schema.definition.required` included `result` or was empty.  
2. **Handshake:** optional `dispute_policy` on accept (API change: persisted on contract; invalid values fall back to `refund`).  
3. **Client orchestration:** six jobs run one-after-another vs six threads issuing the same pipeline concurrently.

---

## Results (2026-04-08, local API + temp DB)

- **Exp 1 - Verification strictness (6 agents: 3 strict + 3 loose):**  
  - **Expected:** Strict arm rejects verification (missing `result`); loose arm verifies and settles.  
  - **Observed:** 3/3 strict runs failed verify with `Missing required field: result`; 3/3 loose runs verified and settled. **Match rate: 6/6.**

- **Exp 2 - Policy fidelity (6 agents: 3× refund + 3× arbitration):**  
  - **Expected:** Verify response `action` equals the contract’s `dispute_policy`.  
  - **Observed:** `refund` → `action: refund` (3/3); `arbitration` → `action: arbitration` (3/3). **Match rate: 6/6.**

- **Exp 3 - Parallel vs sequential (6 agents × 2 batches):**  
  - **Expected:** Parallel wall time lower when work is independent and the server scales.  
  - **Observed:** Sequential wall **0.113 s**, parallel **0.14 s**, success **100%** both. Parallel was **slower** here (~**0.8×** “speedup”), consistent with **SQLite single-writer + connection churn** on one process, not network-bound RTT.

---

## Key takeaways

1. **Structured output requirements are an effective gate:** Without changing the deliverable, tightening the schema flipped outcomes predictably-useful for agent “tool” policies that map to machine-checkable contracts.  
2. **Handshake policy is honored on failure:** `dispute_policy` flows through to verification’s `action`, which supports different downstream automations (auto-refund vs escalate).  
3. **Performance experiments must match deployment reality:** On a single-node SQLite MVP, client-side parallelism does not imply server-side speedup; re-run Exp 3 against a **cloud-hosted API + Postgres** (or pooled DB) to measure real coordination/latency gains.

**Artifacts:** `experiments/run_agent_experiments.py`, raw JSON run output (see `experiments/results/2026-04-08_local-coordinator.json`). For OpenClaw (or similar), implement the same sequence as tools calling `POST /jobs`, `/handshake/accept`, `/fund`, `/start`, `/submit`, `/verify`, `/settle` with fresh `Idempotency-Key` headers per mutation.

---

## Addendum - assignment-complete track (exp4–5, trials, LLM, cloud)

| **4** | **Failure recovery** | Empty deliverable → verify fails → `POST /refund` → terminal `refunded` | Single job; validates escrow exit path after bad work |
| **5** | **Memory strategy A vs B (real LLM)** | OpenAI **rich** vs **minimal** system prompt before generating deliverable JSON | Same strict schema + happy path; compare **settle rate**, **tokens**, rough **USD** (`experiments/llm_escrow_agent.py`) |

- **Repeated trials:** `--trials N` or dashboard field; response includes `trial_results[]` and `aggregate` (mean OK rates, exp3 timing, exp4 refund success rate, exp5 arm means when LLM ran).  
- **Cloud:** `Dockerfile` + `experiments/CLOUD_RUNBOOK.md` — deploy API once; run clients from multiple VMs with `INSTANCE_LABEL` / registered `doer_ids`.  
- **Dependencies:** `openai` in `requirements.txt` for exp5 (optional if you never enable LLM).
