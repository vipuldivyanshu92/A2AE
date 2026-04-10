"""
Real LLM agent for escrow experiments (memory strategy A vs B).

Uses OpenAI Chat Completions to produce deliverable JSON; the harness then runs
the normal escrow HTTP lifecycle. Set OPENAI_API_KEY. Optional: OPENAI_EXPERIMENT_MODEL (default gpt-4o-mini).

Compatible pattern for OpenClaw / other frameworks: replace `llm_complete_json` with your runner
that returns the same deliverable shape.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import uuid

import httpx


def _idem() -> str:
    return str(uuid.uuid4())


def _headers(idem: str, instance_label: str) -> dict[str, str]:
    return {
        "Idempotency-Key": idem,
        "Content-Type": "application/json",
        "X-Experiment-Instance": instance_label,
    }


def _task_request(
    *,
    task_description: str,
    strict_required_keys: list[str] | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "max_budget": "100",
        "task_description": task_description,
        "callback_url": None,
    }
    if strict_required_keys:
        body["output_schema"] = {
            "type": "json-schema",
            "definition": {"required": strict_required_keys},
        }
    else:
        body["output_schema"] = {"type": "json-schema", "definition": {}}
    return body


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def llm_complete_json(
    *,
    system_prompt: str,
    user_prompt: str,
    model: str,
) -> tuple[dict[str, Any], dict[str, int]]:
    """Returns (parsed_json, usage_dict with prompt_tokens, completion_tokens)."""
    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError("Install openai package: pip install openai") from e

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    msg = resp.choices[0].message.content or "{}"
    raw = _strip_json_fence(msg)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Model output is not a JSON object")
    u = resp.usage
    usage = {
        "prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
    }
    return data, usage


def _run_happy_path_with_content(
    client: httpx.Client,
    base: str,
    instance_label: str,
    *,
    agent_id: str,
    deliverable_content: dict[str, Any],
) -> dict[str, Any]:
    spec = _task_request(
        task_description=f"{agent_id} LLM memory experiment",
        strict_required_keys=["result"],
    )
    r = client.post(
        f"{base}/jobs",
        json=spec,
        headers=_headers(_idem(), instance_label),
        timeout=60.0,
    )
    r.raise_for_status()
    job_id = r.json()["job_id"]

    r = client.post(
        f"{base}/jobs/{job_id}/handshake/accept",
        json={"doer_id": agent_id},
        headers=_headers(_idem(), instance_label),
        timeout=60.0,
    )
    r.raise_for_status()
    r = client.post(
        f"{base}/jobs/{job_id}/fund",
        headers=_headers(_idem(), instance_label),
        timeout=60.0,
    )
    r.raise_for_status()
    r = client.post(f"{base}/jobs/{job_id}/start", timeout=60.0)
    r.raise_for_status()

    packet = {
        "deliverable": {"content": deliverable_content, "mime_type": "application/json"},
        "evidence": [],
    }
    r = client.post(
        f"{base}/jobs/{job_id}/submit",
        json=packet,
        headers=_headers(_idem(), instance_label),
        timeout=60.0,
    )
    r.raise_for_status()
    r = client.post(f"{base}/jobs/{job_id}/verify", timeout=60.0)
    r.raise_for_status()
    vj = r.json()
    verified = bool(vj.get("verified"))
    settled = False
    if verified:
        r = client.post(
            f"{base}/jobs/{job_id}/settle",
            headers=_headers(_idem(), instance_label),
            timeout=60.0,
        )
        r.raise_for_status()
        settled = True
    return {
        "job_id": job_id,
        "verified": verified,
        "settled": settled,
        "raw_verify": vj,
    }


SYSTEM_RICH = """You are an autonomous agent completing escrow-backed tasks.
The deliverable.content MUST be a JSON object with a string field "result" (required by the job output schema).
Never use other top-level keys as the primary answer without also including "result".
Respond with ONLY a raw JSON object, no markdown fences."""

SYSTEM_MINIMAL = """You reply with JSON only."""


USER_TASK = """Task: Write a one-sentence status line for job completion.
Return only a JSON object like {"result": "your sentence here"}."""


def estimate_cost_usd(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Rough USD estimate for reporting (not billing). gpt-4o-mini style defaults."""
    # USD per 1M tokens — approximate; adjust if you use another model
    if "gpt-4o-mini" in model or "4o-mini" in model:
        inp, out = 0.15, 0.60
    elif "gpt-4o" in model:
        inp, out = 2.50, 10.0
    else:
        inp, out = 0.50, 1.50
    return (prompt_tokens / 1_000_000) * inp + (completion_tokens / 1_000_000) * out


def run_exp5_llm_memory_ab(
    *,
    base: str,
    instance_label: str,
    trials_per_arm: int = 3,
    model: str | None = None,
    httpx_client: httpx.Client | None = None,
) -> dict[str, Any]:
    """
    Memory strategy A (rich system prompt) vs B (minimal) — real LLM calls.
    Each trial: model produces deliverable → full escrow happy path.
    """
    model = model or os.environ.get("OPENAI_EXPERIMENT_MODEL", "gpt-4o-mini")
    if not os.environ.get("OPENAI_API_KEY"):
        return {
            "skipped": True,
            "reason": "OPENAI_API_KEY not set",
            "hint": "Export OPENAI_API_KEY or use a cloud secret; optional OPENAI_EXPERIMENT_MODEL.",
        }

    arms_out: dict[str, Any] = {}
    total_prompt = total_completion = 0
    t0 = time.perf_counter()

    close_client = False
    if httpx_client is None:
        httpx_client = httpx.Client()
        close_client = True

    try:
        for arm, system in (("memory_rich", SYSTEM_RICH), ("memory_minimal", SYSTEM_MINIMAL)):
            trials = []
            for i in range(trials_per_arm):
                agent_id = f"llm-{instance_label}-{arm}-{i + 1}"
                t_trial = time.perf_counter()
                usage_row: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}
                err: str | None = None
                deliverable: dict[str, Any] = {}
                try:
                    deliverable, usage_row = llm_complete_json(
                        system_prompt=system,
                        user_prompt=USER_TASK,
                        model=model,
                    )
                    total_prompt += usage_row["prompt_tokens"]
                    total_completion += usage_row["completion_tokens"]
                    path = _run_happy_path_with_content(
                        httpx_client,
                        base,
                        instance_label,
                        agent_id=agent_id,
                        deliverable_content=deliverable,
                    )
                    ok = bool(path.get("settled"))
                except Exception as e:
                    path = {}
                    ok = False
                    err = str(e)
                trials.append(
                    {
                        "trial_index": i,
                        "agent_id": agent_id,
                        "ok": ok,
                        "deliverable": deliverable,
                        "usage": usage_row,
                        "escrow": path,
                        "error": err,
                        "elapsed_s": round(time.perf_counter() - t_trial, 3),
                    }
                )
            settled_n = sum(1 for x in trials if x["ok"])
            arms_out[arm] = {
                "trials": trials,
                "settled_rate": settled_n / max(trials_per_arm, 1),
                "settled_count": settled_n,
            }

        wall = time.perf_counter() - t0
        cost = estimate_cost_usd(model, total_prompt, total_completion)
        return {
            "skipped": False,
            "model": model,
            "trials_per_arm": trials_per_arm,
            "arms": arms_out,
            "total_usage": {
                "prompt_tokens": total_prompt,
                "completion_tokens": total_completion,
                "estimated_usd": round(cost, 6),
            },
            "wall_s": round(wall, 3),
        }
    finally:
        if close_client:
            httpx_client.close()
