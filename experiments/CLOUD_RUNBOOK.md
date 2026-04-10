# Cloud + multi-instance agents (OpenClaw-compatible)

This runbook closes the course rubric: **real HTTP clients on different machines**, **≥6 agent identities**, **3+ experiments**, optional **OpenAI** for memory A/B (exp5).

## 1. Deploy the escrow API (one regional service)

Build and run the container (example):

```bash
docker build -t agentic-escrow .
docker run -p 8000:8000 -v escrow-data:/data agentic-escrow
```

Or deploy the same image to **Cloud Run**, **Fly.io**, **ECS**, etc. Note the **public HTTPS origin** (e.g. `https://escrow-xx.run.app`).

Set `ESCROW_DATABASE_URL` to a **persistent** SQLite path or switch to Postgres for production load.

## 2. Run scripted suites from multiple VMs

On **each** cloud VM (or teammate laptop), install the repo and run against the **same** `ESCROW_API_BASE`:

```bash
export ESCROW_API_BASE=https://your-escrow.example.com
export INSTANCE_LABEL=aws-worker-1   # unique per instance
pip install -r requirements.txt
python experiments/run_agent_experiments.py --only all --trials 3
```

- Use **six distinct `doer_id` values** (see UI **Agents** tab or `--doer-id` future flag); today you can pass them via the dashboard **POST /experiments/run** body `doer_ids`.
- `INSTANCE_LABEL` prefixes synthetic IDs when you do not pass `doer_ids`.

## 3. OpenClaw or other frameworks

OpenClaw (or LangGraph, Temporal worker, etc.) should implement the **same REST sequence** as `experiments/run_agent_experiments.py`:

`POST /jobs` → handshake → fund → start → submit → verify → settle/refund.

Use your registered **`doer_id`** at handshake. No global API key in v0; use `Idempotency-Key` on mutating requests.

## 4. Real LLM experiment (memory A vs B)

On a machine with outbound HTTPS:

```bash
export OPENAI_API_KEY=sk-...
export OPENAI_EXPERIMENT_MODEL=gpt-4o-mini   # optional
export ESCROW_API_BASE=https://your-escrow.example.com
python experiments/run_agent_experiments.py --only 5 --include-llm --llm-trials-per-arm 5
```

Or from the UI: suite **5**, enable **Include LLM (exp5)**.

## 5. Assignment checklist

| Rubric item | How you satisfy it |
|-------------|-------------------|
| ≥6 agents | Six `doer_id` slots / six synthetic agents per suite |
| 3+ experiments | Exp1–3 (protocol) + **exp4** recovery + **exp5** LLM memory (optional key) |
| Cloud | Deploy API + run clients from **≥2** instances with different `INSTANCE_LABEL` |
| Repeated trials | `--trials N` or dashboard **Trials** field |
| Cost/latency | Exp3 timing; exp5 **token usage + estimated_usd** (rough) |
| Failure recovery | **Exp4** refund after failed verify |
