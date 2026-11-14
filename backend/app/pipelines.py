"""Read-only API over pipeline run state written by scripts/pipeline.sh (artifacts/runs/).

GET  /api/pipelines                          run summaries, newest first
GET  /api/pipelines/{run_id}                 full run.json
GET  /api/pipelines/{run_id}/logs/{job}      plain-text job log
POST /api/pipelines/{run_id}/approve         record an approval decision for a waiting stage

Security: identifiers are validated against strict patterns AND every resolved path must stay
inside PIPELINE_RUNS_DIR, so path traversal is rejected twice. The approve endpoint has NO
authentication: it is a local demo convenience. In a real deployment it must sit behind
authentication/authorisation (e.g. Entra ID + an approvers group) - Azure Pipelines itself
gates production with Environment approvals instead.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

log = logging.getLogger(__name__)

RUN_ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")
JOB_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
MAX_LOG_BYTES = 2_000_000
SUMMARY_FIELDS = (
    "runId",
    "runNumber",
    "pipeline",
    "branch",
    "commit",
    "trigger",
    "status",
    "startedAt",
    "finishedAt",
)

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: Literal["approve", "reject"]
    comment: str | None = Field(default=None, max_length=500)


def _runs_root(request: Request) -> Path | None:
    root = request.app.state.pipeline_runs_dir
    return Path(root).resolve() if root else None


def _safe_child(root: Path, *parts: str) -> Path:
    path = root.joinpath(*parts).resolve()
    if not path.is_relative_to(root):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid path")
    return path


def _run_dir(request: Request, run_id: str) -> Path:
    if not RUN_ID_RE.fullmatch(run_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid run id")
    root = _runs_root(request)
    if root is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pipeline runs are not available here")
    run_dir = _safe_child(root, run_id)
    if not (run_dir / "run.json").is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    return run_dir


def _read_run(run_dir: Path) -> dict[str, Any]:
    for _ in range(10):  # the pipeline replaces run.json atomically; retry a transient read
        try:
            return json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        except (json.JSONDecodeError, PermissionError):
            time.sleep(0.05)
    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "run state is being written; retry")


def _write_run(run_dir: Path, data: dict[str, Any]) -> None:
    tmp = run_dir / f"run.json.api-{os.getpid()}.tmp"
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, run_dir / "run.json")


@router.get("")
def list_runs(request: Request, limit: int = 50) -> list[dict[str, Any]]:
    root = _runs_root(request)
    if root is None or not root.is_dir():
        return []
    runs = []
    for run_dir in root.iterdir():
        if not (
            run_dir.is_dir()
            and RUN_ID_RE.fullmatch(run_dir.name)
            and (run_dir / "run.json").is_file()
        ):
            continue
        try:
            data = _read_run(run_dir)
        except HTTPException:
            continue
        runs.append({k: data.get(k) for k in SUMMARY_FIELDS})
    runs.sort(key=lambda r: r.get("startedAt") or "", reverse=True)
    return runs[: max(1, min(limit, 200))]


@router.get("/{run_id}")
def get_run(run_id: str, request: Request) -> dict[str, Any]:
    return _read_run(_run_dir(request, run_id))


@router.get("/{run_id}/logs/{job}", response_class=PlainTextResponse)
def get_job_log(run_id: str, job: str, request: Request) -> PlainTextResponse:
    if not JOB_RE.fullmatch(job):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid job name")
    run_dir = _run_dir(request, run_id)
    path = _safe_child(run_dir, "logs", f"{job}.log")
    if not path.is_file():
        return PlainTextResponse("", headers={"Cache-Control": "no-store"})  # job not started yet
    with path.open("rb") as fh:
        size = path.stat().st_size
        fh.seek(max(0, size - MAX_LOG_BYTES))
        text = fh.read().decode("utf-8", errors="replace")
    return PlainTextResponse(text, headers={"Cache-Control": "no-store"})


@router.post("/{run_id}/approve")
def approve(run_id: str, body: ApprovalRequest, request: Request) -> dict[str, Any]:
    # NOTE: no authentication on purpose (local demo). See module docstring before exposing this.
    run_dir = _run_dir(request, run_id)
    data = _read_run(run_dir)
    approval = data.get("approval")
    if (
        not approval
        or approval.get("decision") is not None
        or data.get("status") != "waitingApproval"
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "this run is not waiting for approval")
    approval.update(
        decision="approved" if body.decision == "approve" else "rejected",
        decidedAt=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        decidedBy="anonymous (no auth - local demo)",
        comment=body.comment,
    )
    _write_run(run_dir, data)
    log.info(
        "pipeline approval recorded",
        extra={"fields": {"run_id": run_id, "decision": approval["decision"]}},
    )
    return data
