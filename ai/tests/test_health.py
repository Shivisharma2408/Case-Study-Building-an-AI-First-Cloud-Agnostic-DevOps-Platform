from __future__ import annotations

import json
import subprocess
from typing import Any

from aiops.config import AIConfig
from aiops.health import (
    Finding,
    HealthSignals,
    PodSignal,
    ProbeSignal,
    analyse,
    decide_rollback,
    evaluate_rules,
    previous_good_revision,
    run_health_gate,
)
from tests.conftest import FakeLLM


def signals(**overrides: Any) -> HealthSignals:
    base: dict[str, Any] = dict(
        namespace="staging",
        release="idea-board",
        pods=[PodSignal("idea-board-backend-1", "backend", "Running", True, 0)],
        warning_events=[],
        error_log_lines=[],
        error_log_count=0,
        log_line_count=50,
        probe=ProbeSignal("http://x", 10, 0, 20.0, {"200": 10}),
        helm_history=[{"revision": 1, "status": "superseded"}, {"revision": 2, "status": "deployed"}],
    )
    base.update(overrides)
    return HealthSignals(**base)


def severities(findings: list[Finding]) -> set[str]:
    return {f.severity for f in findings}


def test_healthy_release_has_no_findings() -> None:
    assert evaluate_rules(signals()) == []


def test_crashloop_is_critical() -> None:
    pod = PodSignal("p", "backend", "Running", False, 5, waiting_reasons=["CrashLoopBackOff"])
    findings = evaluate_rules(signals(pods=[pod]))
    assert "critical" in severities(findings)
    assert any("CrashLoopBackOff" in f.message for f in findings)


def test_image_pull_failure_is_critical() -> None:
    pod = PodSignal("p", "backend", "Pending", False, 0, waiting_reasons=["ImagePullBackOff"])
    assert "critical" in severities(evaluate_rules(signals(pods=[pod])))


def test_probe_errors_are_critical_and_latency_is_warning() -> None:
    assert "critical" in severities(evaluate_rules(signals(probe=ProbeSignal("u", 10, 3, 10, {"502": 3}))))
    assert severities(evaluate_rules(signals(probe=ProbeSignal("u", 10, 0, 2500, {"200": 10})))) == {"warning"}


def test_single_restart_and_few_errors_are_warnings() -> None:
    pod = PodSignal("p", "backend", "Running", True, 1)
    assert severities(evaluate_rules(signals(pods=[pod], error_log_count=2))) == {"warning"}


def test_no_pods_is_critical() -> None:
    assert "critical" in severities(evaluate_rules(signals(pods=[])))


def test_failed_install_relabelled_superseded_is_not_a_rollback_target() -> None:
    # Real helm history observed on kind: rev 1 failed, rev 2 good, rev 3 failed.
    failed_install = {"revision": 1, "status": "superseded", "description": "Release failed: context deadline exceeded"}
    hist = [
        failed_install,
        {"revision": 2, "status": "superseded", "description": "Upgrade complete"},
        {"revision": 3, "status": "failed", "description": "Upgrade failed"},
    ]
    assert previous_good_revision(hist) == 2
    assert previous_good_revision([failed_install, {"revision": 2, "status": "failed", "description": "x"}]) is None


def test_previous_good_revision() -> None:
    assert previous_good_revision([{"revision": 1, "status": "deployed"}]) is None
    hist = [
        {"revision": 1, "status": "superseded"},
        {"revision": 2, "status": "failed"},
        {"revision": 3, "status": "deployed"},
    ]
    assert previous_good_revision(hist) == 1


def _verdict(cfg: AIConfig, s: HealthSignals, reply: Any) -> Any:
    return analyse(s, evaluate_rules(s), cfg, FakeLLM(reply))  # type: ignore[arg-type]


def test_llm_cannot_veto_rule_mandated_rollback(cfg: AIConfig) -> None:
    s = signals(pods=[PodSignal("p", "backend", "Running", False, 4, waiting_reasons=["CrashLoopBackOff"])])
    v = _verdict(
        cfg,
        s,
        {
            "healthy": True,
            "confidence": 0.99,
            "summary": "all good",
            "suspected_cause": "",
            "recommended_action": "none",
            "evidence": [],
        },
    )
    assert v.source == "llm"
    assert decide_rollback(evaluate_rules(s), v).rollback is True


def test_llm_escalation_needs_corroboration(cfg: AIConfig) -> None:
    reply = {
        "healthy": False,
        "confidence": 0.95,
        "summary": "suspicious",
        "suspected_cause": "x",
        "recommended_action": "rollback",
        "evidence": [],
    }
    clean = signals()
    d = decide_rollback(evaluate_rules(clean), _verdict(cfg, clean, reply))
    assert d.rollback is False and d.llm_advisory

    noisy = signals(error_log_count=5, error_log_lines=["p: Traceback ..."])
    d = decide_rollback(evaluate_rules(noisy), _verdict(cfg, noisy, reply))
    assert d.rollback is True and "LLM escalation" in d.reason


def test_contradictory_llm_verdict_is_rejected(cfg: AIConfig) -> None:
    v = _verdict(
        cfg,
        signals(),
        {
            "healthy": True,
            "confidence": 1,
            "summary": "s",
            "suspected_cause": "",
            "recommended_action": "rollback",
            "evidence": [],
        },
    )
    assert v.source == "fallback"


def test_fallback_summary_mentions_findings(cfg: AIConfig) -> None:
    s = signals(pods=[PodSignal("p", "backend", "Pending", False, 0, waiting_reasons=["ImagePullBackOff"])])
    v = analyse(s, evaluate_rules(s), cfg, FakeLLM(ready=False))  # type: ignore[arg-type]
    assert v.source == "fallback"
    assert "UNHEALTHY" in v.value.summary and "ImagePullBackOff" in v.value.summary


class FakeCluster:
    """Answers kubectl/helm calls made by the health gate."""

    def __init__(self, pods: list[dict[str, Any]], history: list[dict[str, Any]], rollback_rc: int = 0) -> None:
        self.pods, self.history, self.rollback_rc = pods, history, rollback_rc
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        out, rc = "", 0
        if argv[0] == "kubectl" and "pods" in argv:
            out = json.dumps({"items": self.pods})
        elif argv[0] == "kubectl" and "events" in argv:
            out = json.dumps({"items": []})
        elif argv[0] == "kubectl" and "logs" in argv:
            out = '{"level": "ERROR", "msg": "boom"}\n'
        elif argv[0] == "helm" and "history" in argv:
            out = json.dumps(self.history)
        elif argv[0] == "helm" and "rollback" in argv:
            rc = self.rollback_rc
        return subprocess.CompletedProcess(argv, rc, out, "")


def _pod(reason: str | None) -> dict[str, Any]:
    state = {"waiting": {"reason": reason}} if reason else {"running": {}}
    return {
        "metadata": {"name": "idea-board-backend-abc", "labels": {"app.kubernetes.io/component": "backend"}},
        "status": {
            "phase": "Running",
            "containerStatuses": [{"ready": reason is None, "restartCount": 3 if reason else 0, "state": state}],
        },
    }


def test_gate_rolls_back_and_writes_incident(cfg: AIConfig) -> None:
    cluster = FakeCluster(
        [_pod("CrashLoopBackOff")], [{"revision": 1, "status": "superseded"}, {"revision": 2, "status": "deployed"}]
    )
    report = run_health_gate(
        namespace="staging",
        release="idea-board",
        context="kind-idea-board",
        base_url=None,
        host=None,
        config=cfg,
        run=cluster,
        client=FakeLLM(ready=False),
        echo=lambda _: None,
    )  # type: ignore[arg-type]
    assert report.rolled_back and report.exit_code == 2
    rollback = next(c for c in cluster.calls if "rollback" in c)
    assert rollback[:3] == ["helm", "--kube-context", "kind-idea-board"] and "1" in rollback
    incident = cfg.artifacts_dir / "incidents"
    text = next(incident.iterdir()).read_text(encoding="utf-8")
    assert "CrashLoopBackOff" in text and "rolled back to revision 1" in text
    assert (cfg.artifacts_dir / "health" / "staging-idea-board.json").exists()


def test_gate_first_install_cannot_roll_back(cfg: AIConfig) -> None:
    cluster = FakeCluster([_pod("ImagePullBackOff")], [{"revision": 1, "status": "deployed"}])
    report = run_health_gate(
        namespace="staging",
        release="idea-board",
        context="kind-idea-board",
        base_url=None,
        host=None,
        config=cfg,
        run=cluster,
        client=FakeLLM(ready=False),
        echo=lambda _: None,
    )  # type: ignore[arg-type]
    assert not report.rolled_back and report.exit_code == 3
    assert not any("rollback" in c for c in cluster.calls)


def test_gate_healthy(cfg: AIConfig) -> None:
    cluster = FakeCluster([_pod(None)], [{"revision": 1, "status": "deployed"}])
    cluster_logs_clean = FakeCluster.__call__

    def clean(self: FakeCluster, argv: list[str]) -> subprocess.CompletedProcess[str]:
        proc = cluster_logs_clean(self, argv)
        if "logs" in argv:
            return subprocess.CompletedProcess(argv, 0, '{"level": "INFO"}\n', "")
        return proc

    report = run_health_gate(
        namespace="staging",
        release="idea-board",
        context="kind-idea-board",
        base_url=None,
        host=None,
        config=cfg,
        run=lambda a: clean(cluster, a),
        client=FakeLLM(ready=False),  # type: ignore[arg-type]
        echo=lambda _: None,
    )
    assert report.healthy and report.exit_code == 0 and report.incident_path is None
