"""Tests for GET /jobs (live feed) — filtering, pagination, ordering."""

from __future__ import annotations


def test_empty_list(client) -> None:
    r = client.get("/jobs")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["jobs"] == []


def test_list_returns_recent_first(client, helpers) -> None:
    j1 = helpers.full_settle("bob")
    j2 = helpers.full_refund("bob")
    j3 = helpers.full_settle("alice")
    rows = client.get("/jobs").json()["jobs"]
    ids = [r["job_id"] for r in rows]
    # most recently updated should be first (j3)
    assert ids[0] == j3
    assert set(ids) == {j1, j2, j3}


def test_filter_by_status(client, helpers) -> None:
    helpers.full_settle("bob")
    helpers.full_refund("bob")
    settled = client.get("/jobs?status=settled").json()["jobs"]
    refunded = client.get("/jobs?status=refunded").json()["jobs"]
    assert all(j["status"] == "settled" for j in settled)
    assert all(j["status"] == "refunded" for j in refunded)


def test_filter_by_doer(client, helpers) -> None:
    helpers.full_settle("bob")
    helpers.full_settle("carol")
    bob_jobs = client.get("/jobs?doer_id=bob").json()["jobs"]
    assert all(j["doer_id"] == "bob" for j in bob_jobs)
    assert len(bob_jobs) == 1


def test_limit_pagination(client, helpers) -> None:
    for _ in range(5):
        helpers.full_settle("bob")
    page1 = client.get("/jobs?limit=2&offset=0").json()
    page2 = client.get("/jobs?limit=2&offset=2").json()
    assert page1["count"] == 2 and page2["count"] == 2
    overlap = {j["job_id"] for j in page1["jobs"]} & {j["job_id"] for j in page2["jobs"]}
    assert overlap == set()
