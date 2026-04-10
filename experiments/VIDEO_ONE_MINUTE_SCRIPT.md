# ~1-minute video: experiment setup & findings

**Audience:** Teammates / reviewers who want proof the escrow MVP is tested like a system.

**Visuals:** Split or picture-in-picture: terminal or log view + optional architecture slide (3 boxes: “Agent clients (cloud)” → “Escrow API” → “DB / ledger”).

---

### 0:00–0:12 — Hook & goal  
“We stopped demoing happy paths and ran **three controlled experiments** against the escrow API: **six labeled doer agents** per wave, comparing **verification strictness**, **dispute policy**, and **parallel vs sequential** job completion.”

### 0:12–0:28 — Setup (b-roll: `uvicorn`, env vars, script)  
“**Setup:** API on a host with `ESCROW_DATABASE_URL` for a clean DB; clients use `experiments/run_agent_experiments.py` with `ESCROW_API_BASE` and `INSTANCE_LABEL` per machine. On cloud, you’d point the base URL at the deployed API and run the same script from **different instances** so each run shows up as a distinct `doer_id` prefix.”

### 0:28–0:48 — What we changed & results (on-screen table or bullets)  
“**Experiment 1:** strict `output_schema` with required `result` vs loose schema—same wrong-shaped JSON. Strict: **verify failed every time**; loose: **settled every time**.  
**Experiment 2:** handshake `dispute_policy` **refund vs arbitration** on the same failure—the verify payload’s **`action` matched the policy** three for three each.  
**Experiment 3:** six full lifecycles **sequential vs parallel**—**both 100% success**; locally, parallel was slightly **slower** because SQLite serializes writes.”

### 0:48–1:00 — Takeaway  
“**Takeaway:** contract shape and handshake policy behave deterministically; **throughput experiments belong on the real cloud DB** you’ll use in production. Details and numbers are in `experiments/EXPERIMENT_SUMMARY.md`.”

---

**Optional closing shot:** Scroll `EXPERIMENT_SUMMARY.md` or flash the JSON snippet in `experiments/results/`.
