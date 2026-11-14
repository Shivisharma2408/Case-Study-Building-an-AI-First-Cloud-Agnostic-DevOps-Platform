from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

RUN_A = "20261114-100000-aaaa"
RUN_B = "20261114-110000-bbbb"


def make_run(
    root: Path, run_id: str, started: str, status: str = "succeeded", **extra: Any
) -> Path:
    run_dir = root / run_id
    (run_dir / "logs").mkdir(parents=True)
    data = {
        "schemaVersion": 1,
        "runId": run_id,
        "runNumber": "20261114.1",
        "pipeline": "idea-board",
        "branch": "main",
        "commit": "abc123",
        "trigger": "manual",
        "status": status,
        "startedAt": started,
        "finishedAt": None,
        "stages": [
            {
                "name": "build",
                "status": status,
                "jobs": [{"name": "build", "logPath": "logs/build.log"}],
            }
        ],
        "approval": None,
        "aiArtifacts": [],
        "incident": None,
        **extra,
    }
    (run_dir / "run.json").write_text(json.dumps(data), encoding="utf-8")
    (run_dir / "logs" / "build.log").write_bytes(b"step 1\nstep 2\n")  # bytes: no CRLF on Windows
    return run_dir


@pytest.fixture
def runs_root(tmp_path: Path) -> Path:
    root = tmp_path / "runs"
    make_run(root, RUN_A, "2026-11-14T10:00:00Z")
    make_run(
        root,
        RUN_B,
        "2026-11-14T11:00:00Z",
        status="waitingApproval",
        approval={"stage": "promote-production", "decision": None},
    )
    (tmp_path / "secret.txt").write_text("top secret", encoding="utf-8")
    return root


@pytest.fixture
def client(runs_root: Path) -> Iterator[TestClient]:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:", pipeline_runs_dir=str(runs_root)
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_list_runs_newest_first(client: TestClient) -> None:
    runs = client.get("/api/pipelines").json()
    assert [r["runId"] for r in runs] == [RUN_B, RUN_A]
    assert "stages" not in runs[0]  # summaries only


def test_get_run(client: TestClient) -> None:
    body = client.get(f"/api/pipelines/{RUN_A}").json()
    assert body["runId"] == RUN_A and body["stages"][0]["name"] == "build"


def test_get_log_is_plain_text(client: TestClient) -> None:
    resp = client.get(f"/api/pipelines/{RUN_A}/logs/build")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert resp.text == "step 1\nstep 2\n"


def test_missing_log_is_empty_not_error(client: TestClient) -> None:
    resp = client.get(f"/api/pipelines/{RUN_A}/logs/deploy-staging")
    assert resp.status_code == 200 and resp.text == ""


def test_unknown_run_is_404(client: TestClient) -> None:
    assert client.get("/api/pipelines/20990101-000000-ffff").status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/api/pipelines/..%2Fsecret.txt",
        "/api/pipelines/..%2F..%2Fetc",
        f"/api/pipelines/{RUN_A}/logs/..%2F..%2F..%2Fsecret",
        f"/api/pipelines/{RUN_A}/logs/build.log",
        f"/api/pipelines/{RUN_A}/logs/BUILD",
        "/api/pipelines/not-a-run-id",
    ],
)
def test_path_traversal_and_bad_ids_are_rejected(client: TestClient, path: str) -> None:
    resp = client.get(path)
    assert resp.status_code in (400, 404)
    assert "top secret" not in resp.text


def test_approve_records_decision(client: TestClient, runs_root: Path) -> None:
    resp = client.post(
        f"/api/pipelines/{RUN_B}/approve", json={"decision": "approve", "comment": "ship it"}
    )
    assert resp.status_code == 200
    stored = json.loads((runs_root / RUN_B / "run.json").read_text(encoding="utf-8"))
    assert stored["approval"]["decision"] == "approved"
    assert stored["approval"]["comment"] == "ship it"
    assert stored["approval"]["decidedAt"]
    # a second decision is a conflict
    assert (
        client.post(f"/api/pipelines/{RUN_B}/approve", json={"decision": "reject"}).status_code
        == 409
    )


def test_reject_records_decision(client: TestClient, runs_root: Path) -> None:
    assert (
        client.post(f"/api/pipelines/{RUN_B}/approve", json={"decision": "reject"}).status_code
        == 200
    )
    stored = json.loads((runs_root / RUN_B / "run.json").read_text(encoding="utf-8"))
    assert stored["approval"]["decision"] == "rejected"


def test_approve_requires_waiting_run(client: TestClient) -> None:
    assert (
        client.post(f"/api/pipelines/{RUN_A}/approve", json={"decision": "approve"}).status_code
        == 409
    )


def test_approve_validates_body(client: TestClient) -> None:
    resp = client.post(f"/api/pipelines/{RUN_B}/approve", json={"decision": "maybe"})
    assert resp.status_code == 422


def test_runs_disabled_without_directory() -> None:
    settings = Settings(database_url="sqlite+pysqlite:///:memory:")
    with TestClient(create_app(settings)) as c:
        assert c.get("/api/pipelines").json() == []
        assert c.get(f"/api/pipelines/{RUN_A}").status_code == 404
