"""
pytest fixtures for the Agent Escrow API.

Each test gets a fresh, isolated SQLite database in a temp directory by
setting `ESCROW_DATABASE_URL` *before* the app modules are imported. The
fixture imports the app inside the function so the env var is honored,
then exposes a `TestClient` and a `Helpers` object with the common
lifecycle building blocks.
"""

from __future__ import annotations

import importlib
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _idem() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def app(tmp_path, monkeypatch):
    db_path = tmp_path / "escrow_test.db"
    monkeypatch.setenv("ESCROW_DATABASE_URL", f"sqlite:///{db_path}")

    # Re-import the relevant modules so they pick up the new DB URL.
    for mod in list(sys.modules):
        if mod == "main" or mod.startswith("src.escrow"):
            del sys.modules[mod]

    main_mod = importlib.import_module("main")
    return main_mod.app


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


class Helpers:
    """Tiny lifecycle builder so each test reads as plain English."""

    def __init__(self, client) -> None:
        self.c = client

    def make_job(
        self, *, required: list[str] | None = None, requester_id: str | None = None
    ) -> str:
        spec: dict[str, Any] = {
            "max_budget": "100",
            "task_description": "test job",
            "callback_url": None,
        }
        if requester_id:
            spec["requester_id"] = requester_id
        if required is not None:
            spec["output_schema"] = {
                "type": "json-schema",
                "definition": {"required": required},
            }
        else:
            spec["output_schema"] = {"type": "json-schema", "definition": {}}
        r = self.c.post("/jobs", json=spec, headers={"Idempotency-Key": _idem()})
        assert r.status_code == 200, r.text
        return r.json()["job_id"]

    def accept(self, job_id: str, doer_id: str, policy: str = "refund") -> None:
        r = self.c.post(
            f"/jobs/{job_id}/handshake/accept",
            json={"doer_id": doer_id, "dispute_policy": policy},
            headers={"Idempotency-Key": _idem()},
        )
        assert r.status_code == 200, r.text

    def fund(self, job_id: str) -> None:
        r = self.c.post(f"/jobs/{job_id}/fund", headers={"Idempotency-Key": _idem()})
        assert r.status_code == 200, r.text

    def start(self, job_id: str) -> None:
        r = self.c.post(f"/jobs/{job_id}/start")
        assert r.status_code == 200, r.text

    def submit(self, job_id: str, content: dict[str, Any]) -> None:
        r = self.c.post(
            f"/jobs/{job_id}/submit",
            json={
                "deliverable": {"content": content, "mime_type": "application/json"},
                "evidence": [],
            },
            headers={"Idempotency-Key": _idem()},
        )
        assert r.status_code == 200, r.text

    def verify(self, job_id: str) -> dict[str, Any]:
        r = self.c.post(f"/jobs/{job_id}/verify")
        assert r.status_code == 200, r.text
        return r.json()

    def settle(self, job_id: str) -> None:
        r = self.c.post(f"/jobs/{job_id}/settle", headers={"Idempotency-Key": _idem()})
        assert r.status_code == 200, r.text

    def refund(self, job_id: str) -> None:
        r = self.c.post(f"/jobs/{job_id}/refund", headers={"Idempotency-Key": _idem()})
        assert r.status_code == 200, r.text

    def full_settle(self, doer_id: str = "bob", requester_id: str | None = None) -> str:
        jid = self.make_job(required=["result"], requester_id=requester_id)
        self.accept(jid, doer_id)
        self.fund(jid)
        self.start(jid)
        self.submit(jid, {"result": "ok"})
        v = self.verify(jid)
        assert v["verified"] is True
        self.settle(jid)
        return jid

    def full_refund(self, doer_id: str = "bob", requester_id: str | None = None) -> str:
        jid = self.make_job(required=["result"], requester_id=requester_id)
        self.accept(jid, doer_id, policy="refund")
        self.fund(jid)
        self.start(jid)
        self.submit(jid, {"answer": "wrong-shape"})
        v = self.verify(jid)
        assert v["verified"] is False
        self.refund(jid)
        return jid


@pytest.fixture
def helpers(client) -> Helpers:
    return Helpers(client)
