"""Intelligent post-deploy health analysis, automatic rollback and incident summaries.

Pipeline: collect signals (pods, restarts, waiting reasons, warning events, error logs,
synthetic HTTP probe, helm history) -> deterministic rules -> LLM analysis -> decision.

Safety contract: the deterministic rules are authoritative for hard failures. The LLM can
add caution (escalate to a rollback when *corroborated* by at least one warning signal)
and it writes the human-readable summary, but it can never veto a rule-mandated rollback.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from .commands import ROLLBACK_POLICY, Command, execute
from .config import AIConfig
from .llm import AIDecision, OllamaClient, ValidationFailedError, decide, schema_errors

BAD_WAITING_REASONS = {
    "CrashLoopBackOff",
    "ImagePullBackOff",
    "ErrImagePull",
    "CreateContainerConfigError",
    "CreateContainerError",
    "InvalidImageName",
    "RunContainerError",
}
# Backend: JSON logs (5xx responses are logged at ERROR). Frontend: nginx error-log levels.
_ERROR_LINE = re.compile(r'"level":\s*"(ERROR|CRITICAL)"|Traceback|\bFATAL\b|\[(error|crit|alert|emerg)\]', re.I)

Severity = Literal["critical", "warning"]


@dataclass
class Finding:
    severity: Severity
    message: str


@dataclass
class PodSignal:
    name: str
    component: str
    phase: str
    ready: bool
    restarts: int
    waiting_reasons: list[str] = field(default_factory=list)
    terminated_reasons: list[str] = field(default_factory=list)


@dataclass
class ProbeSignal:
    base_url: str
    requests: int
    errors: int
    p95_ms: float
    status_counts: dict[str, int]

    @property
    def error_rate(self) -> float:
        return self.errors / self.requests if self.requests else 1.0


@dataclass
class HealthSignals:
    namespace: str
    release: str
    pods: list[PodSignal]
    warning_events: list[str]
    error_log_lines: list[str]
    error_log_count: int
    log_line_count: int
    probe: ProbeSignal | None
    helm_history: list[dict[str, Any]]
    deploy_failed: bool = False


# --------------------------------------------------------------------------- collection

Run = Callable[[list[str]], subprocess.CompletedProcess[str]]


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, timeout=120, check=False)


def _kubectl_json(run: Run, context: str, *args: str) -> dict[str, Any]:
    proc = run(["kubectl", "--context", context, *args, "-o", "json"])
    if proc.returncode != 0:
        return {"items": []}
    return json.loads(proc.stdout or "{}")


def _pod_signals(pods_json: dict[str, Any]) -> list[PodSignal]:
    pods = []
    for item in pods_json.get("items", []):
        if item.get("metadata", {}).get("deletionTimestamp"):
            continue  # terminating pods from the previous ReplicaSet are not part of this release
        status = item.get("status", {})
        statuses = status.get("containerStatuses", []) + status.get("initContainerStatuses", [])
        waiting = [s["state"]["waiting"].get("reason", "") for s in statuses if "waiting" in s.get("state", {})]
        terminated = [
            s.get("lastState", {}).get("terminated", {}).get("reason", "")
            for s in statuses
            if s.get("lastState", {}).get("terminated")
        ]
        pods.append(
            PodSignal(
                name=item["metadata"]["name"],
                component=item["metadata"].get("labels", {}).get("app.kubernetes.io/component", "?"),
                phase=status.get("phase", "Unknown"),
                ready=bool(statuses) and all(s.get("ready") for s in statuses),
                restarts=sum(int(s.get("restartCount", 0)) for s in statuses),
                waiting_reasons=[w for w in waiting if w],
                terminated_reasons=[t for t in terminated if t],
            )
        )
    return pods


def probe(base_url: str, host: str | None, count: int = 10, timeout: float = 5.0) -> ProbeSignal:
    """Synthetic traffic: the closest thing to request metrics without a metrics stack."""
    paths = ["/healthz", "/api/ideas", "/"]
    latencies: list[float] = []
    statuses: dict[str, int] = {}
    errors = 0
    for i in range(count):
        url = base_url.rstrip("/") + paths[i % len(paths)]
        req = urllib.request.Request(url, headers={"Host": host} if host else {})  # noqa: S310
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                code = str(resp.status)
        except urllib.error.HTTPError as exc:
            code = str(exc.code)
        except (urllib.error.URLError, TimeoutError, OSError):
            code = "conn_error"
        latencies.append((time.perf_counter() - start) * 1000)
        statuses[code] = statuses.get(code, 0) + 1
        if not code.startswith(("2", "3")):
            errors += 1
    latencies.sort()
    p95 = latencies[max(0, int(round(0.95 * len(latencies))) - 1)] if latencies else 0.0
    return ProbeSignal(base_url, count, errors, round(p95, 1), statuses)


def collect(
    namespace: str,
    release: str,
    context: str,
    *,
    base_url: str | None,
    host: str | None,
    deploy_failed: bool = False,
    run: Run = _run,
) -> HealthSignals:
    selector = f"app.kubernetes.io/instance={release}"
    pods = _pod_signals(_kubectl_json(run, context, "get", "pods", "-n", namespace, "-l", selector))

    events_json = _kubectl_json(run, context, "get", "events", "-n", namespace, "--field-selector", "type=Warning")
    events = []
    for ev in events_json.get("items", [])[-50:]:
        obj = ev.get("involvedObject", {}).get("name", "")
        if obj.startswith(release) or ev.get("reason") in {"FailedScheduling", "FailedCreate"}:
            events.append(f"{ev.get('reason')}: {obj}: {ev.get('message', '')[:200]}")
    events = events[-15:]

    error_lines: list[str] = []
    total_lines = 0
    for pod in pods:
        for previous in [False, True] if pod.restarts else [False]:
            argv = [
                "kubectl",
                "--context",
                context,
                "logs",
                pod.name,
                "-n",
                namespace,
                "--all-containers",
                "--tail=200",
            ]
            if previous:
                argv.append("--previous")
            proc = run(argv)
            if proc.returncode != 0:
                continue
            lines = proc.stdout.splitlines()
            total_lines += len(lines)
            error_lines += [f"{pod.name}: {ln[:300]}" for ln in lines if _ERROR_LINE.search(ln)]

    hist = run(["helm", "--kube-context", context, "history", release, "-n", namespace, "-o", "json", "--max", "10"])
    history = json.loads(hist.stdout) if hist.returncode == 0 and hist.stdout.strip() else []

    return HealthSignals(
        namespace=namespace,
        release=release,
        pods=pods,
        warning_events=events,
        error_log_lines=error_lines[-30:],
        error_log_count=len(error_lines),
        log_line_count=total_lines,
        probe=probe(base_url, host) if base_url else None,
        helm_history=history,
        deploy_failed=deploy_failed,
    )


# --------------------------------------------------------------------------- rules


def evaluate_rules(s: HealthSignals) -> list[Finding]:
    f: list[Finding] = []
    if s.deploy_failed:
        f.append(Finding("critical", "helm upgrade --wait did not converge (timeout or failed resources)"))
    if not s.pods:
        f.append(Finding("critical", "no pods found for the release"))
    for p in s.pods:
        bad = sorted(set(p.waiting_reasons) & BAD_WAITING_REASONS)
        if bad:
            f.append(Finding("critical", f"pod {p.name} is waiting: {', '.join(bad)}"))
        if "OOMKilled" in p.terminated_reasons:
            f.append(Finding("critical", f"pod {p.name} was OOMKilled"))
        if p.restarts >= 2:
            f.append(Finding("critical", f"pod {p.name} restarted {p.restarts} times"))
        elif p.restarts == 1:
            f.append(Finding("warning", f"pod {p.name} restarted once"))
        if not p.ready and not bad:
            f.append(Finding("critical", f"pod {p.name} is not ready (phase {p.phase})"))
    if s.probe:
        if s.probe.error_rate > 0.05:
            f.append(
                Finding("critical", f"synthetic probe error rate {s.probe.error_rate:.0%} ({s.probe.status_counts})")
            )
        elif s.probe.p95_ms > 1500:
            f.append(Finding("warning", f"synthetic probe p95 latency {s.probe.p95_ms:.0f}ms"))
    if s.error_log_count >= 20:
        f.append(Finding("critical", f"{s.error_log_count} error log lines since rollout"))
    elif s.error_log_count:
        f.append(Finding("warning", f"{s.error_log_count} error log line(s) since rollout"))
    if s.warning_events:
        f.append(Finding("warning", f"{len(s.warning_events)} Kubernetes warning event(s)"))
    return f


# --------------------------------------------------------------------------- LLM analysis

VERDICT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["healthy", "confidence", "summary", "suspected_cause", "recommended_action", "evidence"],
    "properties": {
        "healthy": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "summary": {"type": "string", "minLength": 1, "maxLength": 1200},
        "suspected_cause": {"type": "string", "maxLength": 600},
        "recommended_action": {"enum": ["none", "monitor", "investigate", "rollback"]},
        "evidence": {"type": "array", "maxItems": 8, "items": {"type": "string", "maxLength": 300}},
    },
}

SYSTEM_PROMPT = """You are an SRE assistant analysing a Kubernetes release right after deployment.
Use ONLY the signals provided; do not invent data. Output ONLY JSON matching the schema.
Write `summary` for an on-call engineer: what is wrong (or that all is well), impact, and what to check.
Recommend "rollback" only when signals show user impact or a failing release."""


@dataclass
class Verdict:
    healthy: bool
    confidence: float
    summary: str
    suspected_cause: str
    recommended_action: str
    evidence: list[str]


def _deterministic_verdict(s: HealthSignals, findings: list[Finding]) -> Verdict:
    critical = [x.message for x in findings if x.severity == "critical"]
    warnings = [x.message for x in findings if x.severity == "warning"]
    if critical:
        summary = (
            f"Release '{s.release}' in '{s.namespace}' is UNHEALTHY: {len(critical)} critical finding(s). "
            + " ".join(f"- {c}." for c in critical)
        )
        cause = critical[0]
        action = "rollback"
    elif warnings:
        summary = f"Release '{s.release}' in '{s.namespace}' is healthy with {len(warnings)} warning(s): " + "; ".join(
            warnings
        )
        cause, action = "", "monitor"
    else:
        summary = f"Release '{s.release}' in '{s.namespace}' is healthy: all pods ready, probe clean, no error logs."
        cause, action = "", "none"
    evidence = (critical + warnings + s.warning_events[:2] + s.error_log_lines[:2])[:8]
    return Verdict(not critical, 1.0, summary, cause, action, [e[:300] for e in evidence])


def _signals_for_prompt(s: HealthSignals, findings: list[Finding]) -> str:
    data = asdict(s)
    data["helm_history"] = [
        {k: h.get(k) for k in ("revision", "status", "description", "app_version")} for h in s.helm_history[-5:]
    ]
    data["rule_findings"] = [asdict(x) for x in findings]
    return json.dumps(data, default=str)[:12000]


def analyse(
    s: HealthSignals, findings: list[Finding], config: AIConfig, client: OllamaClient | None = None
) -> AIDecision[Verdict]:
    def parse(data: Any) -> Verdict:
        errors = schema_errors(data, VERDICT_SCHEMA)
        if errors:
            raise ValidationFailedError(errors)
        v = Verdict(**data)
        if v.healthy and v.recommended_action == "rollback":
            raise ValidationFailedError(["contradiction: healthy=true but recommended_action=rollback"])
        return v

    return decide(
        feature=f"health-{s.namespace}",
        system=SYSTEM_PROMPT,
        prompt="Signals collected after the deployment:\n" + _signals_for_prompt(s, findings),
        schema=VERDICT_SCHEMA,
        parse=parse,
        fallback=lambda: _deterministic_verdict(s, findings),
        config=config,
        client=client,
        context={"namespace": s.namespace, "release": s.release},
        summarize=asdict,
    )


# --------------------------------------------------------------------------- decision + rollback


@dataclass
class Decision:
    rollback: bool
    reason: str
    llm_advisory: str | None = None


def decide_rollback(findings: list[Finding], verdict: AIDecision[Verdict]) -> Decision:
    critical = [x for x in findings if x.severity == "critical"]
    warnings = [x for x in findings if x.severity == "warning"]
    if critical:
        return Decision(True, f"rules: {len(critical)} critical finding(s) (authoritative)")
    v = verdict.value
    if verdict.source == "llm" and not v.healthy and v.recommended_action == "rollback":
        if v.confidence >= 0.8 and warnings:
            return Decision(
                True,
                f"LLM escalation (confidence {v.confidence:.2f}) corroborated by {len(warnings)} warning signal(s)",
            )
        return Decision(
            False,
            "healthy by rules",
            llm_advisory="LLM suggested rollback without corroborating signals; recorded as advisory only",
        )
    return Decision(False, "healthy by rules" + (" (with warnings)" if warnings else ""))


def previous_good_revision(history: list[dict[str, Any]]) -> int | None:
    if len(history) < 2:
        return None
    current = max(int(h["revision"]) for h in history)
    good = [
        int(h["revision"])
        for h in history
        if int(h["revision"]) < current and h.get("status") in {"superseded", "deployed"}
    ]
    return max(good) if good else None


def write_incident(
    out_dir: Path,
    s: HealthSignals,
    findings: list[Finding],
    verdict: AIDecision[Verdict],
    decision: Decision,
    rollback_note: str,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    path = out_dir / f"{now:%Y%m%dT%H%M%SZ}-{s.namespace}-{s.release}.md"
    v = verdict.value
    current = max((int(h["revision"]) for h in s.helm_history), default=0)
    lines = [
        f"# Incident: {s.release} in {s.namespace}",
        "",
        f"- **Detected:** {now:%Y-%m-%d %H:%M:%S} UTC by the post-deploy health gate",
        f"- **Release revision:** {current}",
        f"- **Decision:** {'ROLLBACK' if decision.rollback else 'no rollback'} - {decision.reason}",
        f"- **Rollback:** {rollback_note}",
        f"- **Analysis source:** {verdict.banner}",
        f"- **Audit record:** `{verdict.audit_path.name if verdict.audit_path else 'n/a'}`",
        "",
        "## Summary",
        "",
        v.summary,
        "",
    ]
    if v.suspected_cause:
        lines += ["## Suspected cause", "", v.suspected_cause, ""]
    lines += ["## Rule findings", "", "| Severity | Finding |", "|---|---|"]
    lines += [f"| {x.severity} | {x.message} |" for x in findings] or ["| - | none |"]
    lines += [
        "",
        "## Pods",
        "",
        "| Pod | Component | Phase | Ready | Restarts | Waiting |",
        "|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {p.name} | {p.component} | {p.phase} | {p.ready} | {p.restarts} | {', '.join(p.waiting_reasons) or '-'} |"
        for p in s.pods
    ]
    if s.probe:
        lines += [
            "",
            "## Synthetic probe",
            "",
            f"{s.probe.requests} requests to {s.probe.base_url}: "
            f"{s.probe.errors} errors, p95 {s.probe.p95_ms} ms, statuses {s.probe.status_counts}",
        ]
    if s.warning_events:
        lines += ["", "## Warning events", "", *[f"- {e}" for e in s.warning_events]]
    if s.error_log_lines:
        lines += ["", "## Error log excerpt", "", "```", *s.error_log_lines[:15], "```"]
    if decision.llm_advisory:
        lines += ["", f"> Note: {decision.llm_advisory}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@dataclass
class HealthReport:
    healthy: bool
    rolled_back: bool
    exit_code: int
    findings: list[Finding]
    verdict: Verdict
    verdict_source: str
    decision: Decision
    incident_path: str | None


def run_health_gate(
    *,
    namespace: str,
    release: str,
    context: str,
    base_url: str | None,
    host: str | None,
    config: AIConfig,
    deploy_failed: bool = False,
    auto_rollback: bool = True,
    settle_seconds: int = 0,
    echo: Callable[[str], None] = print,
    run: Run = _run,
    client: OllamaClient | None = None,
) -> HealthReport:
    if settle_seconds:
        echo(f"waiting {settle_seconds}s for the release to settle...")
        time.sleep(settle_seconds)
    signals = collect(namespace, release, context, base_url=base_url, host=host, deploy_failed=deploy_failed, run=run)
    findings = evaluate_rules(signals)
    verdict = analyse(signals, findings, config, client)
    decision = decide_rollback(findings, verdict)

    echo(verdict.banner)
    echo(f"verdict: {'HEALTHY' if not decision.rollback else 'UNHEALTHY'} - {decision.reason}")
    for x in findings:
        echo(f"  [{x.severity}] {x.message}")
    echo("summary: " + verdict.value.summary)

    rolled_back, incident, exit_code = False, None, 0
    if decision.rollback:
        exit_code = 3
        target = previous_good_revision(signals.helm_history)
        if not auto_rollback:
            note = "automatic rollback disabled"
        elif target is None:
            note = "no previous good revision (first install) - manual action required"
        else:
            cmd = Command(
                ("helm", "rollback", release, str(target), "-n", namespace, "--wait", "--timeout", "5m"),
                "Roll back to the last good revision",
            )
            results = execute([cmd], ROLLBACK_POLICY, namespace, context, runner=run, echo=echo)
            if results and results[-1].returncode == 0:
                rolled_back, exit_code = True, 2
                note = f"rolled back to revision {target} successfully"
            else:
                note = f"rollback to revision {target} FAILED: {results[-1].stderr.strip()[:300] if results else ''}"
        echo(note)
        incident = write_incident(config.artifacts_dir / "incidents", signals, findings, verdict, decision, note)
        echo(f"incident summary written to {incident}")

    report = HealthReport(
        healthy=not decision.rollback,
        rolled_back=rolled_back,
        exit_code=exit_code,
        findings=findings,
        verdict=verdict.value,
        verdict_source=verdict.source,
        decision=decision,
        incident_path=str(incident) if incident else None,
    )
    out = config.artifacts_dir / "health"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{namespace}-{release}.json").write_text(
        json.dumps({"report": asdict(report), "signals": asdict(signals)}, indent=2, default=str), encoding="utf-8"
    )
    return report
