"""Top-level smoke tests: health, landing, swagger, full lifecycle, AI verifier."""

from __future__ import annotations


def test_health(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_landing_page_is_served(client) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Agent" in r.text and "Escrow" in r.text


def test_static_site_assets_are_served(client) -> None:
    for path in ("/site/app.css", "/site/app.js", "/site/agents.html", "/site/jobs.html", "/site/run.html"):
        r = client.get(path)
        assert r.status_code == 200, f"{path} -> {r.status_code}"


def test_single_origin_deploy_everything_on_one_port(client) -> None:
    """Railway exposes one $PORT per service. Verify every public surface
    (landing, hosted UI, API, Swagger, OpenAPI, health) responds 200 from
    the same TestClient — i.e. the same process and port."""
    surfaces = [
        "/",
        "/health",
        "/docs",
        "/openapi.json",
        "/site/agents.html",
        "/site/jobs.html",
        "/site/run.html",
        "/site/app.css",
        "/site/app.js",
        "/agents",
        "/jobs",
    ]
    for path in surfaces:
        r = client.get(path)
        assert r.status_code == 200, f"{path} -> {r.status_code}"


def test_railway_json_uses_dockerfile_and_health_check() -> None:
    """The deploy config must use the Dockerfile builder and pin /health.

    `startCommand` is intentionally NOT set in railway.json: Railway
    invokes it argv-style (no shell), so `--port ${PORT}` would reach
    uvicorn as a literal string. The Dockerfile CMD runs through
    `sh -c` and is the single source of truth for the start command.
    """
    import json
    from pathlib import Path

    cfg = json.loads((Path(__file__).resolve().parent.parent / "railway.json").read_text())
    assert cfg["build"]["builder"] == "DOCKERFILE"
    assert cfg["deploy"]["healthcheckPath"] == "/health"
    # Guard the regression: do not put startCommand back in railway.json
    # without wrapping it in `sh -c '...'` (and even then, prefer the
    # Dockerfile CMD).
    assert "startCommand" not in cfg["deploy"]


def test_dockerfile_cmd_uses_sh_c_for_port_expansion() -> None:
    """Dockerfile CMD must expand $PORT through a shell."""
    from pathlib import Path

    df = (Path(__file__).resolve().parent.parent / "Dockerfile").read_text()
    cmd_lines = [line for line in df.splitlines() if line.strip().startswith("CMD ")]
    assert cmd_lines, "Dockerfile is missing a CMD line"
    cmd = cmd_lines[-1]
    assert '"sh"' in cmd and '"-c"' in cmd, f"CMD must run through sh -c, got: {cmd}"
    assert "${PORT" in cmd, f"CMD must reference $PORT, got: {cmd}"


def test_openapi_lists_new_routes(client) -> None:
    spec = client.get("/openapi.json").json()
    paths = set(spec["paths"].keys())
    assert "/agents" in paths
    assert "/agents/{agent_id}" in paths
    assert "/jobs" in paths
    assert "/jobs/{job_id}/trace" in paths
    assert "/jobs/{job_id}/verify_ai" in paths
    assert "/jobs/{job_id}/verify_trace" in paths
    assert "/experiments/scale/run" in paths


def test_full_settle_lifecycle(client, helpers) -> None:
    jid = helpers.full_settle()
    snap = client.get(f"/jobs/{jid}").json()
    assert snap["status"] == "settled"


def test_full_refund_lifecycle(client, helpers) -> None:
    jid = helpers.full_refund()
    snap = client.get(f"/jobs/{jid}").json()
    assert snap["status"] == "refunded"


def test_ai_verifier_heuristic_for_settled_job(client, helpers) -> None:
    jid = helpers.full_settle()
    r = client.post(f"/jobs/{jid}/verify_trace", json={"backend": "heuristic"})
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "accept"
    assert body["score"] == 1.0
    assert body["issues"] == []
    assert body["deterministic_snapshot"]["verified"] is True


def test_ai_verifier_heuristic_for_refunded_job(client, helpers) -> None:
    jid = helpers.full_refund()
    r = client.post(f"/jobs/{jid}/verify_trace", json={"backend": "heuristic"})
    assert r.status_code == 200
    body = r.json()
    # Verdict should be either reject or needs_review and clearly flag the deliverable issue.
    assert body["verdict"] in {"reject", "needs_review"}
    assert any("missing_required_field" in i for i in body["issues"])
    assert body["deterministic_snapshot"]["verified"] is False
    assert body["deterministic_snapshot"]["action"] == "refund"
