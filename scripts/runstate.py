#!/usr/bin/env python3
"""Run-state writer for scripts/pipeline.sh (stdlib only).

Maintains artifacts/runs/<runId>/run.json while a run progresses so the Pipelines UI
(GET /api/pipelines/...) can show live status. Writes are atomic (tmp file + replace).

    runstate.py init --runs-root DIR --plan "lint-test build promote-production:deploy-production+verify-production" ...
    runstate.py --run-dir DIR stage-start STAGE
    runstate.py --run-dir DIR job-start STAGE JOB
    runstate.py --run-dir DIR job-end STAGE JOB STATUS
    runstate.py --run-dir DIR stage-end STAGE STATUS
    runstate.py --run-dir DIR wait-approval STAGE [--timeout SEC]   exit 0 approved, 3 rejected, 4 timed out
    runstate.py --run-dir DIR decide approve|reject [--by NAME]       (CLI alternative to the UI)
    runstate.py --run-dir DIR collect-ai --audit-dir DIR --incidents-dir DIR
    runstate.py --run-dir DIR finish STATUS
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATUSES = {
    "pending",
    "running",
    "succeeded",
    "failed",
    "skipped",
    "rolledBack",
    "waitingApproval",
}
AI_KINDS = {
    "env-config": "helm-values",
    "preview-plan": "deploy-plan",
    "health": "health-summary",
    "geniac": "iac-sizing",
}


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load(run_dir: Path) -> dict[str, Any]:
    for _ in range(20):  # a reader/writer may be replacing the file right now
        try:
            return json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        except (json.JSONDecodeError, PermissionError):
            time.sleep(0.1)
    return json.loads((run_dir / "run.json").read_text(encoding="utf-8"))


def save(run_dir: Path, data: dict[str, Any]) -> None:
    tmp = run_dir / f"run.json.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    for attempt in range(50):
        try:
            os.replace(tmp, run_dir / "run.json")
            return
        except PermissionError:  # Windows: target briefly open by a reader
            if attempt == 49:
                raise
            time.sleep(0.1)


def find(data: dict[str, Any], stage: str, job: str | None = None) -> dict[str, Any]:
    st = next((s for s in data["stages"] if s["name"] == stage), None)
    if st is None:
        raise SystemExit(f"runstate: unknown stage {stage!r}")
    if job is None:
        return st
    jb = next((j for j in st["jobs"] if j["name"] == job), None)
    if jb is None:
        jb = {
            "name": job,
            "status": "pending",
            "startedAt": None,
            "finishedAt": None,
            "durationSec": None,
            "logPath": f"logs/{job}.log",
        }
        st["jobs"].append(jb)
    return jb


def seconds_between(start: str | None, end: str | None) -> int | None:
    a, b = parse_ts(start), parse_ts(end)
    return int((b - a).total_seconds()) if a and b else None


def check_status(status: str) -> str:
    if status not in STATUSES:
        raise SystemExit(f"runstate: invalid status {status!r}")
    return status


# --------------------------------------------------------------------------- commands


def cmd_init(a: argparse.Namespace) -> None:
    root = Path(a.runs_root)
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC)
    run_id = f"{stamp:%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
    same_day = [p for p in root.iterdir() if p.is_dir() and p.name.startswith(f"{stamp:%Y%m%d}-")]
    stages = []
    for spec in a.plan.split():
        name, _, jobs = spec.partition(":")
        stages.append(
            {
                "name": name,
                "status": "pending",
                "startedAt": None,
                "finishedAt": None,
                "jobs": [
                    {
                        "name": j,
                        "status": "pending",
                        "startedAt": None,
                        "finishedAt": None,
                        "durationSec": None,
                        "logPath": f"logs/{j}.log",
                    }
                    for j in (jobs.split("+") if jobs else [name])
                ],
            }
        )
    run_dir = root / run_id
    (run_dir / "logs").mkdir(parents=True)
    save(
        run_dir,
        {
            "schemaVersion": 1,
            "runId": run_id,
            "runNumber": f"{stamp:%Y%m%d}.{len(same_day) + 1}",
            "pipeline": a.pipeline,
            "branch": a.branch,
            "commit": a.commit,
            "commitMessage": a.commit_message,
            "trigger": a.trigger,
            "triggerDetail": a.trigger_detail,
            "startedAt": now(),
            "finishedAt": None,
            "status": "running",
            "stages": stages,
            "approval": None,
            "aiArtifacts": [],
            "incident": None,
        },
    )
    print(run_dir.as_posix())


def cmd_stage_start(a: argparse.Namespace) -> None:
    data = load(a.run_dir)
    st = find(data, a.stage)
    st.update(status="running", startedAt=st["startedAt"] or now(), finishedAt=None)
    data["status"] = "running"
    save(a.run_dir, data)


def cmd_job_start(a: argparse.Namespace) -> None:
    data = load(a.run_dir)
    jb = find(data, a.stage, a.job)
    jb.update(status="running", startedAt=now(), finishedAt=None, durationSec=None)
    save(a.run_dir, data)


def cmd_job_end(a: argparse.Namespace) -> None:
    data = load(a.run_dir)
    jb = find(data, a.stage, a.job)
    jb.update(status=check_status(a.status), finishedAt=now())
    jb["durationSec"] = seconds_between(jb["startedAt"], jb["finishedAt"])
    save(a.run_dir, data)


def cmd_stage_end(a: argparse.Namespace) -> None:
    data = load(a.run_dir)
    st = find(data, a.stage)
    st.update(status=check_status(a.status), finishedAt=now())
    for jb in st["jobs"]:
        if jb["status"] == "pending":
            jb["status"] = "skipped"
    save(a.run_dir, data)


def cmd_wait_approval(a: argparse.Namespace) -> int:
    data = load(a.run_dir)
    st = find(data, a.stage)
    st.update(status="waitingApproval", startedAt=st["startedAt"] or now())
    data["status"] = "waitingApproval"
    data["approval"] = {
        "stage": a.stage,
        "decision": None,
        "requestedAt": now(),
        "decidedAt": None,
        "decidedBy": None,
        "comment": None,
    }
    save(a.run_dir, data)
    deadline = time.monotonic() + a.timeout
    while time.monotonic() < deadline:
        time.sleep(2)
        decision = (load(a.run_dir).get("approval") or {}).get("decision")
        if decision in ("approved", "rejected"):
            data = load(a.run_dir)
            st = find(data, a.stage)
            if decision == "approved":
                st["status"] = "running"
                data["status"] = "running"
                save(a.run_dir, data)
                return 0
            st.update(status="skipped", finishedAt=now())
            save(a.run_dir, data)
            return 3
    data = load(a.run_dir)
    data["approval"].update(decision="timedOut", decidedAt=now(), decidedBy="system")
    find(data, a.stage).update(status="skipped", finishedAt=now())
    save(a.run_dir, data)
    return 4


def cmd_decide(a: argparse.Namespace) -> int:
    data = load(a.run_dir)
    approval = data.get("approval")
    if not approval or approval.get("decision") is not None:
        print("runstate: no pending approval for this run", file=sys.stderr)
        return 1
    approval.update(
        decision="approved" if a.decision == "approve" else "rejected",
        decidedAt=now(),
        decidedBy=a.by,
        comment=a.comment,
    )
    save(a.run_dir, data)
    print(f"{approval['decision']} {data['runId']}")
    return 0


def _kind(feature: str) -> str:
    for prefix, kind in AI_KINDS.items():
        if feature.startswith(prefix):
            return kind
    return feature


def _stage_at(data: dict[str, Any], ts: datetime) -> str | None:
    for st in data["stages"]:
        start, end = parse_ts(st["startedAt"]), parse_ts(st["finishedAt"])
        if start and start <= ts and (end is None or ts <= end):
            return st["name"]
    return None


def cmd_collect_ai(a: argparse.Namespace) -> None:
    """Attach AI audit records produced during this run (artifacts/ai/audit.jsonl) to run.json."""
    data = load(a.run_dir)
    started = parse_ts(data["startedAt"])
    finished = parse_ts(data["finishedAt"])
    index = Path(a.audit_dir) / "audit.jsonl"
    artifacts = []
    if index.exists():
        for line in index.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = parse_ts(rec.get("timestamp"))
            if not ts or ts < started or (finished and ts > finished):
                continue
            validation = rec.get("validation") or {}
            artifacts.append(
                {
                    "id": rec.get("file"),
                    "kind": _kind(rec.get("feature", "")),
                    "feature": rec.get("feature"),
                    "stage": _stage_at(data, ts),
                    "source": rec.get("source"),
                    "model": rec.get("model"),
                    "prompt": rec.get("prompt"),
                    "rawOutput": rec.get("raw_output"),
                    "output": rec.get("decision"),
                    "validation": {
                        "passed": validation.get("valid"),
                        "errors": validation.get("errors", []),
                    },
                    "fallbackReason": rec.get("fallback_reason"),
                    "timestamp": rec.get("timestamp"),
                }
            )
    data["aiArtifacts"] = artifacts

    if any(st["status"] == "rolledBack" for st in data["stages"]):
        health = [x for x in artifacts if x["kind"] == "health-summary"]
        summary = (health[-1]["output"] or {}).get("summary") if health else None
        report = None
        incidents = Path(a.incidents_dir)
        if incidents.exists():
            recent = [p for p in incidents.glob("*.md") if datetime.fromtimestamp(p.stat().st_mtime, UTC) >= started]
            if recent:
                report = max(recent, key=lambda p: p.stat().st_mtime).read_text(encoding="utf-8")[:20000]
        data["incident"] = {
            "summary": summary or "Release rolled back by the health gate.",
            "report": report,
        }
    save(a.run_dir, data)


def cmd_finish(a: argparse.Namespace) -> None:
    data = load(a.run_dir)
    for st in data["stages"]:
        if st["status"] in ("pending", "waitingApproval"):
            st["status"] = "skipped"
        elif st["status"] == "running":
            st.update(status="failed", finishedAt=now())
        for jb in st["jobs"]:
            if jb["status"] == "pending":
                jb["status"] = "skipped"
            elif jb["status"] == "running":
                jb.update(status="failed", finishedAt=now())
    data.update(status=check_status(a.status), finishedAt=now())
    save(a.run_dir, data)


def main() -> int:
    p = argparse.ArgumentParser(prog="runstate")
    p.add_argument("--run-dir", type=Path)
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init")
    i.add_argument("--runs-root", required=True)
    i.add_argument("--plan", required=True)
    i.add_argument("--pipeline", default="idea-board")
    i.add_argument("--branch", default="unknown")
    i.add_argument("--commit", default="unknown")
    i.add_argument("--commit-message", default="")
    i.add_argument("--trigger", default="manual")
    i.add_argument("--trigger-detail", default="")

    for name in ("stage-start",):
        sub.add_parser(name).add_argument("stage")
    for name in ("job-start",):
        s = sub.add_parser(name)
        s.add_argument("stage")
        s.add_argument("job")
    s = sub.add_parser("job-end")
    s.add_argument("stage")
    s.add_argument("job")
    s.add_argument("status")
    s = sub.add_parser("stage-end")
    s.add_argument("stage")
    s.add_argument("status")
    s = sub.add_parser("wait-approval")
    s.add_argument("stage")
    s.add_argument("--timeout", type=int, default=1800)
    s = sub.add_parser("decide")
    s.add_argument("decision", choices=["approve", "reject"])
    s.add_argument("--by", default="cli")
    s.add_argument("--comment", default=None)
    s = sub.add_parser("collect-ai")
    s.add_argument("--audit-dir", required=True)
    s.add_argument("--incidents-dir", required=True)
    sub.add_parser("finish").add_argument("status")

    a = p.parse_args()
    if a.cmd != "init" and a.run_dir is None:
        p.error("--run-dir is required")
    handler = {
        "init": cmd_init,
        "stage-start": cmd_stage_start,
        "job-start": cmd_job_start,
        "job-end": cmd_job_end,
        "stage-end": cmd_stage_end,
        "wait-approval": cmd_wait_approval,
        "decide": cmd_decide,
        "collect-ai": cmd_collect_ai,
        "finish": cmd_finish,
    }[a.cmd]
    return handler(a) or 0


if __name__ == "__main__":
    sys.exit(main())
