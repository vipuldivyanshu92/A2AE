"""Tests for the public agent registry and per-agent stats."""

from __future__ import annotations


def _register(client, **kwargs):
    body = {
        "agent_id": kwargs["agent_id"],
        "display_name": kwargs.get("display_name", kwargs["agent_id"]),
        "role": kwargs.get("role", "both"),
        "endpoint_url": kwargs.get("endpoint_url"),
        "webhook_url": kwargs.get("webhook_url"),
        "description": kwargs.get("description"),
    }
    r = client.post("/agents", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_register_creates_then_lists(client) -> None:
    _register(client, agent_id="bob", display_name="Bob", role="doer")
    _register(client, agent_id="alice", display_name="Alice", role="requester")

    rows = client.get("/agents").json()
    ids = {r["agent_id"] for r in rows}
    assert {"bob", "alice"} <= ids
    bob = next(r for r in rows if r["agent_id"] == "bob")
    assert bob["role"] == "doer"
    assert bob["stats"]["settled"] == 0


def test_register_is_idempotent_upsert(client) -> None:
    _register(client, agent_id="bob", display_name="Bob v1", role="doer")
    _register(client, agent_id="bob", display_name="Bob v2", role="both", description="updated")
    rows = client.get("/agents").json()
    bob = next(r for r in rows if r["agent_id"] == "bob")
    assert bob["display_name"] == "Bob v2"
    assert bob["role"] == "both"
    assert bob["description"] == "updated"


def test_role_filter(client) -> None:
    _register(client, agent_id="r1", role="requester")
    _register(client, agent_id="d1", role="doer")
    _register(client, agent_id="b1", role="both")

    doers = {a["agent_id"] for a in client.get("/agents?role=doer").json()}
    # role=doer should also include "both" agents (an agent flagged "both" can act as a doer)
    assert "d1" in doers and "b1" in doers
    assert "r1" not in doers


def test_stats_reflect_lifecycle(client, helpers) -> None:
    _register(client, agent_id="bob")
    helpers.full_settle("bob")
    helpers.full_settle("bob")
    helpers.full_refund("bob")

    bob = next(a for a in client.get("/agents").json() if a["agent_id"] == "bob")
    s = bob["stats"]
    assert s["settled"] == 2
    assert s["refunded"] == 1
    assert s["jobs_as_doer"] == 3
    assert abs(s["success_rate"] - (2 / 3)) < 1e-3  # API rounds to 4 decimals


def test_requester_stats_are_attributed(client, helpers) -> None:
    _register(client, agent_id="alice", role="requester")
    _register(client, agent_id="bob", role="doer")
    helpers.full_settle("bob", requester_id="alice")
    helpers.full_settle("bob", requester_id="alice")
    helpers.full_refund("bob", requester_id="alice")

    alice = next(a for a in client.get("/agents").json() if a["agent_id"] == "alice")
    s = alice["stats"]
    assert s["jobs_as_requester"] == 3
    assert s["jobs_as_doer"] == 0
    assert s["settled"] == 2
    assert s["refunded"] == 1


def test_get_agent_returns_recent_jobs(client, helpers) -> None:
    _register(client, agent_id="bob")
    helpers.full_settle("bob")
    helpers.full_refund("bob")

    detail = client.get("/agents/bob").json()
    assert detail["agent"]["agent_id"] == "bob"
    statuses = {j["status"] for j in detail["recent_jobs"]}
    assert {"settled", "refunded"} <= statuses
    assert all(j["role_for_this_agent"] == "doer" for j in detail["recent_jobs"])


def test_delete_removes_registry_entry_but_not_jobs(client, helpers) -> None:
    _register(client, agent_id="bob")
    jid = helpers.full_settle("bob")

    r = client.delete("/agents/bob")
    assert r.status_code == 200

    # Agent gone from registry…
    assert client.get("/agents/bob").status_code == 404

    # …but the job still exists with bob as the doer.
    snap = client.get(f"/jobs/{jid}").json()
    assert snap["doer_id"] == "bob"
    assert snap["status"] == "settled"


def test_sort_by_settled(client, helpers) -> None:
    _register(client, agent_id="alpha")
    _register(client, agent_id="beta")
    helpers.full_settle("beta")
    helpers.full_settle("beta")
    helpers.full_settle("alpha")

    rows = client.get("/agents?sort=settled").json()
    ids = [r["agent_id"] for r in rows]
    assert ids.index("beta") < ids.index("alpha")
