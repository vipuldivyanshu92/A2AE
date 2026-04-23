# HW8 1-minute video (unlisted YouTube) — scaled experiments + AI verifier

**Audience:** Grader / reviewer who already saw the HW7 video.
**Visuals:** Split screen — left: terminal with the `scale_experiment.py` run scrolling; right: the architecture slide and then a small `curl /jobs/{id}/verify_trace` response.

---

### 0:00–0:10 — What changed since HW7 (hook)
"In HW7 we ran six labeled agents against the escrow API on happy paths. For HW8 we pushed past the demo: **30, 60, and 120 real HTTP doer agents** driven from multiple simulated cloud instances, plus a brand-new **AI Verification Engine** that audits both Bob's deliverable and the full Alice↔Bob trace."

### 0:10–0:25 — Scaled setup (b-roll: `scale_experiment.py --agents 120 --instances 8`)
"The scale runner spawns `N` concurrent instance simulators — each with its own `httpx` connection pool, its own thread group, and its own `INSTANCE_LABEL` — which is the exact same code path as running the script from `N` cloud VMs. We also inject a 20% bad-deliverable rate so happy paths and refund paths contend on the server at the same time."

### 0:25–0:40 — What broke (b-roll: the scale table from `EXPERIMENT_SUMMARY_HW8.md`)
"Throughput **flatlines at ~39 jobs per second** regardless of whether we throw 30, 60, or 120 agents at it. p50 lifecycle latency **scales linearly** with load — 0.48 seconds at 30 agents, 1.0 at 60, **2.4 at 120**. That's the classic SQLite single-writer fingerprint: more client concurrency just queues behind one write lock. Zero HTTP errors up to 120, but Postgres + WAL is clearly the next move."

### 0:40–0:55 — AI Verification Engine (b-roll: `curl POST /jobs/{id}/verify_trace` response JSON)
"New in HW8: `/verify_ai` reviews Bob's deliverable, `/verify_trace` audits the whole Alice↔Bob lifecycle — spec, contract, audit log, deliverable, deterministic verdict. It runs on **OpenAI** when a key is set and falls back to a deterministic heuristic so our 30+ agent scale runs don't burn tokens. On a settled job it returns `verdict=accept, score=1.0`. On a bad-deliverable refund it returns `verdict=needs_review` with the **exact issue tag**: `deliverable:missing_required_field:result`, side by side with the deterministic gate's `action: refund`."

### 0:55–1:00 — Takeaway
"Scaling flipped the story: the server is now the bottleneck, not the agents — and the AI verifier caught a real audit-log bug the one-off demos missed. Details in `experiments/EXPERIMENT_SUMMARY_HW8.md`."

---

**Optional closing shot:** flash the JSON snippet `{"verdict":"accept","score":1.0,"issues":[]}` next to the scale table.
