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


def test_html_pages_send_no_store_cache_headers(client) -> None:
    """Regression guard: the hosted UI must NEVER be cached by the browser.

    Without no-store headers, Chrome heuristically caches HTML for ~10 min,
    so a redeploy can leave users on a stale `agents.html` / `app.js` and
    produce confusing 'API returns 2 rows but UI shows 1' symptoms when
    the cached JS is one version behind the cached HTML."""
    for path in ("/", "/site/agents.html", "/site/jobs.html", "/site/run.html"):
        r = client.get(path)
        cc = r.headers.get("cache-control", "")
        assert "no-store" in cc, f"{path}: missing no-store; got cache-control={cc!r}"


def test_static_assets_use_short_revalidating_cache(client) -> None:
    """JS/CSS must NOT be no-store (we want them cached briefly for perf)
    but they MUST also revalidate so a redeploy is picked up quickly."""
    for path in ("/site/app.js", "/site/app.css"):
        r = client.get(path)
        cc = r.headers.get("cache-control", "")
        assert "must-revalidate" in cc, f"{path}: missing must-revalidate; got {cc!r}"
        assert "max-age=60" in cc, f"{path}: expected short max-age; got {cc!r}"


def test_pages_strip_polluted_url_params(client) -> None:
    """Each hosted UI page must clean form-data query params on load.

    A browser GET-submit (legacy bug) could leave the URL stuck on
    `?agent_id=...&display_name=...`. The page must self-heal via
    `history.replaceState` so a refresh shows a clean URL."""
    for path in ("/site/agents.html", "/site/jobs.html", "/site/run.html"):
        html = client.get(path).text
        assert "history.replaceState" in html, f"{path}: missing URL self-clean"
        assert "cleanUrl" in html, f"{path}: cleanUrl IIFE missing"


def test_app_js_is_iife_wrapped_so_globals_dont_collide(client) -> None:
    """Regression guard: app.js MUST be wrapped in an IIFE so it doesn't
    declare top-level `const`s in the global script scope. Without this,
    the per-page inline `<script>` blocks that destructure window.AE
    (e.g. `const { API } = window.AE`) throw
    `Identifier 'API' has already been declared` and the form falls back
    to a default GET submit, putting user input in the URL."""
    src = client.get("/site/app.js").text
    assert src.lstrip().startswith("/*") or src.lstrip().startswith("(function") or "(function ()" in src, src[:200]
    assert "})();" in src or "}());" in src, "app.js IIFE must be closed"
    assert "window.AE" in src, "app.js must export window.AE"


def test_inline_scripts_are_iife_wrapped(client) -> None:
    """The per-page inline scripts also wrap themselves in an IIFE so
    each page's local names don't bleed into other pages or get
    redeclared if a script is included twice."""
    for path in ("/site/agents.html", "/site/jobs.html", "/site/run.html"):
        html = client.get(path).text
        # Locate the inline script that pulls in window.AE.
        marker = "window.AE"
        assert marker in html, f"{path}: missing window.AE usage"
        # The inline block immediately after `<script src="/site/app.js">` must open with `(function`
        # and (eventually) close with `})();`.
        idx = html.find('src="/site/app.js"')
        tail = html[idx:]
        assert "(function" in tail[:600], f"{path}: inline script not wrapped in IIFE"
        assert "})();" in tail, f"{path}: inline IIFE never closed"


def test_forms_have_javascript_void_action(client) -> None:
    """Every <form> in the hosted UI has a defensive `action='javascript:void(0)'`
    so even if the JS handler errors before `e.preventDefault()` is called,
    the form can't accidentally GET-submit user input into the URL."""
    for path in ("/site/agents.html", "/site/run.html"):
        html = client.get(path).text
        # Count <form ... > tags and ensure each has the safety action.
        import re

        forms = re.findall(r"<form\b[^>]*>", html)
        assert forms, f"{path}: no <form> tags found"
        for f in forms:
            assert 'action="javascript:void(0)"' in f, f"{path}: unprotected form: {f}"


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
