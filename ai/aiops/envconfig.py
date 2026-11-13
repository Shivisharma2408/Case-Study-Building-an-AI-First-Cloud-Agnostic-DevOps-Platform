"""Dynamic environment configuration: natural-language goal -> validated Helm values.

The LLM proposes replicas/resources/HPA/PDB for a goal such as "cost-sensitive staging".
The proposal must pass (1) the JSON schema, (2) semantic policy (requests <= limits,
HPA bounds, PDB satisfiable, namespace budget) and (3) the *deterministic* reading of
the goal: if the spec says high availability, the LLM cannot hand back a single replica.
Otherwise the deterministic profile for that goal (the safe default) is used.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from .config import SCHEMA_DIR, AIConfig
from .llm import AIDecision, OllamaClient, ValidationFailedError, decide, schema_errors

Profile = Literal["cost-sensitive", "balanced", "high-availability"]
PROFILE_SCHEMA: dict[str, Any] = json.loads(
    (SCHEMA_DIR / "environment-profile.schema.json").read_text(encoding="utf-8")
)

# Goal words only - environment names ("staging", "production") must not decide the class:
# a staging spec may well say "verify releases before production".
_HA_WORDS = re.compile(
    r"\b(high[- ]availability|highly[- ]available|ha|resilien\w*|mission[- ]critical"
    r"|uptime|zero[- ]downtime|no downtime)\b",
    re.I,
)
_COST_WORDS = re.compile(
    r"\b(cost[- ]sensitive|cost[- ]optimi[sz]ed|cheap\w*|budget|minimal|low[- ]cost|frugal)\b", re.I
)


def classify(spec: str) -> Profile:
    """Deterministic, explainable reading of the goal. HA wins ties: availability is the safer error."""
    if _HA_WORDS.search(spec):
        return "high-availability"
    if _COST_WORDS.search(spec):
        return "cost-sensitive"
    return "balanced"


def _component(
    replicas: int, req: tuple[str, str], lim: tuple[str, str], hpa: tuple[bool, int, int], pdb: bool
) -> dict[str, Any]:
    return {
        "replicaCount": replicas,
        "resources": {"requests": {"cpu": req[0], "memory": req[1]}, "limits": {"cpu": lim[0], "memory": lim[1]}},
        "autoscaling": {
            "enabled": hpa[0],
            "minReplicas": hpa[1],
            "maxReplicas": hpa[2],
            "targetCPUUtilizationPercentage": 70,
        },
        "podDisruptionBudget": {"enabled": pdb, "minAvailable": 1},
    }


SAFE_DEFAULTS: dict[Profile, dict[str, Any]] = {
    "cost-sensitive": {
        "profile": "cost-sensitive",
        "rationale": "Deterministic cost-sensitive profile: single replicas, small requests, no autoscaling.",
        "backend": _component(1, ("50m", "96Mi"), ("250m", "192Mi"), (False, 1, 2), False),
        "frontend": _component(1, ("10m", "32Mi"), ("100m", "64Mi"), (False, 1, 2), False),
        "topologySpread": False,
    },
    "balanced": {
        "profile": "balanced",
        "rationale": "Deterministic balanced profile: one replica that may scale to three under CPU load.",
        "backend": _component(1, ("100m", "128Mi"), ("500m", "256Mi"), (True, 1, 3), False),
        "frontend": _component(1, ("25m", "32Mi"), ("200m", "128Mi"), (False, 1, 2), False),
        "topologySpread": False,
    },
    "high-availability": {
        "profile": "high-availability",
        "rationale": "Deterministic HA profile: >=2 replicas, HPA, PodDisruptionBudgets and spread across nodes.",
        "backend": _component(2, ("100m", "128Mi"), ("500m", "256Mi"), (True, 2, 4), True),
        "frontend": _component(2, ("25m", "32Mi"), ("200m", "128Mi"), (True, 2, 3), True),
        "topologySpread": True,
    },
}


@dataclass(frozen=True)
class Budget:
    """Upper bound on worst-case (maxReplicas x requests) for the namespace's ResourceQuota."""

    cpu_millicores: int = 1000
    memory_mi: int = 1024


def _milli(cpu: str) -> int:
    return int(cpu[:-1])


def _mi(mem: str) -> int:
    return int(mem[:-2])


def policy_errors(profile: dict[str, Any], required: Profile, budget: Budget) -> list[str]:
    errors: list[str] = []
    total_cpu = total_mem = 0
    for name in ("backend", "frontend"):
        c = profile[name]
        req, lim = c["resources"]["requests"], c["resources"]["limits"]
        if _milli(req["cpu"]) > _milli(lim["cpu"]):
            errors.append(f"{name}: cpu request exceeds limit")
        if _mi(req["memory"]) > _mi(lim["memory"]):
            errors.append(f"{name}: memory request exceeds limit")
        if _milli(lim["cpu"]) > 2000 or _mi(lim["memory"]) > 2048:
            errors.append(f"{name}: limits above the per-container ceiling (2000m / 2048Mi)")
        if name == "backend" and _mi(lim["memory"]) < 128:
            errors.append("backend: memory limit below 128Mi will OOM")
        hpa, pdb = c["autoscaling"], c["podDisruptionBudget"]
        if hpa["minReplicas"] > hpa["maxReplicas"]:
            errors.append(f"{name}: autoscaling.minReplicas > maxReplicas")
        effective_min = hpa["minReplicas"] if hpa["enabled"] else c["replicaCount"]
        worst_case = hpa["maxReplicas"] if hpa["enabled"] else c["replicaCount"]
        if pdb["enabled"] and pdb["minAvailable"] >= effective_min:
            errors.append(f"{name}: PDB minAvailable must be below the minimum replica count or drains block")
        if required == "high-availability":
            if effective_min < 2:
                errors.append(f"{name}: high-availability requires at least 2 replicas")
            if not pdb["enabled"]:
                errors.append(f"{name}: high-availability requires a PodDisruptionBudget")
        if required == "cost-sensitive" and worst_case > 2:
            errors.append(f"{name}: cost-sensitive profile may not scale beyond 2 replicas")
        total_cpu += worst_case * _milli(req["cpu"])
        total_mem += worst_case * _mi(req["memory"])
    if total_cpu > budget.cpu_millicores:
        errors.append(f"worst-case CPU requests {total_cpu}m exceed budget {budget.cpu_millicores}m")
    if total_mem > budget.memory_mi:
        errors.append(f"worst-case memory requests {total_mem}Mi exceed budget {budget.memory_mi}Mi")
    if required == "high-availability" and not profile["topologySpread"]:
        errors.append("high-availability requires topologySpread")
    return errors


SYSTEM_PROMPT = """You are a Kubernetes capacity planner. Turn a deployment goal into resource settings.
Output ONLY JSON matching the schema. CPU in millicores like "100m", memory in Mi like "128Mi".
Rules: requests <= limits; PDB minAvailable must be lower than the minimum replica count;
high availability means >= 2 replicas, PDBs and topologySpread; cost-sensitive means at most 2 replicas.
Stay within the namespace budget for worst-case (max replicas x requests)."""


def _prompt(spec: str, environment: str, required: Profile, budget: Budget) -> str:
    return (
        f"Environment: {environment}\nGoal: {spec.strip()}\n"
        f"Deterministic classification of the goal: {required}\n"
        f"Namespace budget for requests: {budget.cpu_millicores}m CPU, {budget.memory_mi}Mi memory\n"
        "Workloads: 'backend' (Python FastAPI, ~60-120Mi RSS, CPU-bound on bursts) and "
        "'frontend' (nginx serving static files, ~10Mi RSS).\n"
        f"Reference profile for this class (adjust if the goal justifies it):\n"
        f"{json.dumps(SAFE_DEFAULTS[required])}"
    )


def propose(
    spec: str,
    environment: str,
    config: AIConfig,
    budget: Budget | None = None,
    client: OllamaClient | None = None,
) -> AIDecision[dict[str, Any]]:
    budget = budget or Budget()
    required = classify(spec)

    def parse(data: Any) -> dict[str, Any]:
        errors = schema_errors(data, PROFILE_SCHEMA)
        if not errors:
            errors = policy_errors(data, required, budget)
        if errors:
            raise ValidationFailedError(errors)
        return data

    def fallback() -> dict[str, Any]:
        profile = copy.deepcopy(SAFE_DEFAULTS[required])
        # Deterministic defaults are held to the same policy; scale down if over budget.
        if policy_errors(profile, required, budget):
            profile = copy.deepcopy(SAFE_DEFAULTS["cost-sensitive"])
        return profile

    return decide(
        feature=f"env-config-{environment}",
        system=SYSTEM_PROMPT,
        prompt=_prompt(spec, environment, required, budget),
        schema=PROFILE_SCHEMA,
        parse=parse,
        fallback=fallback,
        config=config,
        client=client,
        context={
            "environment": environment,
            "spec": spec,
            "required_profile": required,
            "budget": {"cpu_m": budget.cpu_millicores, "memory_mi": budget.memory_mi},
        },
    )


def to_helm_values(decision: AIDecision[dict[str, Any]], environment: str, spec: str) -> str:
    profile = decision.value
    values = {
        "backend": profile["backend"],
        "frontend": profile["frontend"],
        "topologySpread": {"enabled": profile["topologySpread"]},
    }
    header = [
        f"# Generated by aiops env-config for '{environment}'. Do not edit; regenerate instead.",
        f"# Goal: {' '.join(spec.split())[:200]}",
        f"# Profile: {profile['profile']} | source: {decision.source}"
        + (f" ({decision.model})" if decision.source == "llm" else ""),
        f"# {decision.banner}",
        f"# Rationale: {' '.join(profile['rationale'].split())[:300]}",
        f"# Audit: {decision.audit_path.name if decision.audit_path else 'n/a'}",
    ]
    return "\n".join(header) + "\n" + yaml.safe_dump(values, sort_keys=False)


def write_values(decision: AIDecision[dict[str, Any]], environment: str, spec: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_helm_values(decision, environment, spec), encoding="utf-8")
    return out
