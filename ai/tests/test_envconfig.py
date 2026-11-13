from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from aiops.config import REPO_ROOT, AIConfig
from aiops.envconfig import SAFE_DEFAULTS, Budget, classify, policy_errors, propose, to_helm_values
from tests.conftest import FakeLLM, audit_records


@pytest.mark.parametrize(
    ("spec", "profile"),
    [
        ("Cost-sensitive staging. Verify releases before production.", "cost-sensitive"),
        ("High-availability production, zero downtime", "high-availability"),
        ("Just a normal environment", "balanced"),
        ((REPO_ROOT / "deploy/env-specs/staging.txt").read_text(), "cost-sensitive"),
        ((REPO_ROOT / "deploy/env-specs/production.txt").read_text(), "high-availability"),
    ],
)
def test_classify(spec: str, profile: str) -> None:
    assert classify(spec) == profile


@pytest.mark.parametrize("profile", list(SAFE_DEFAULTS))
def test_safe_defaults_satisfy_their_own_policy(profile: str) -> None:
    assert policy_errors(SAFE_DEFAULTS[profile], profile, Budget(1500, 1536)) == []  # type: ignore[arg-type]


def test_valid_llm_profile_is_used(cfg: AIConfig) -> None:
    proposal = copy.deepcopy(SAFE_DEFAULTS["high-availability"])
    proposal["backend"]["autoscaling"]["maxReplicas"] = 3
    proposal["rationale"] = "LLM tuned"
    decision = propose("high availability please", "production", cfg, Budget(1500, 1536), FakeLLM(proposal))  # type: ignore[arg-type]
    assert decision.source == "llm"
    assert decision.value["backend"]["autoscaling"]["maxReplicas"] == 3


def test_llm_cannot_downgrade_high_availability(cfg: AIConfig) -> None:
    proposal = copy.deepcopy(SAFE_DEFAULTS["cost-sensitive"])  # 1 replica, no PDB
    proposal["profile"] = "high-availability"  # lying about it does not help
    decision = propose("high-availability production", "production", cfg, Budget(1500, 1536), FakeLLM(proposal))  # type: ignore[arg-type]
    assert decision.source == "fallback"
    assert decision.value == SAFE_DEFAULTS["high-availability"]
    errors = audit_records(cfg)[-1]["validation"]["errors"]
    assert any("at least 2 replicas" in e for e in errors)


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (lambda p: p["backend"]["resources"]["requests"].update(cpu="900m"), "cpu request exceeds limit"),
        (lambda p: p["backend"].update(replicaCount=50), "replicaCount"),
        (lambda p: p["backend"]["resources"]["limits"].update(memory="lots"), "memory"),
        (lambda p: p["backend"]["podDisruptionBudget"].update(enabled=True, minAvailable=1), "PDB minAvailable"),
        (lambda p: p.update(extra="field"), "Additional properties"),
        (lambda p: p["backend"]["autoscaling"].update(enabled=True, minReplicas=2, maxReplicas=1), "minReplicas"),
    ],
)
def test_invalid_llm_profiles_fall_back(cfg: AIConfig, mutate, error: str) -> None:  # type: ignore[no-untyped-def]
    proposal = copy.deepcopy(SAFE_DEFAULTS["cost-sensitive"])
    mutate(proposal)
    decision = propose("cost-sensitive staging", "staging", cfg, Budget(), FakeLLM(proposal))  # type: ignore[arg-type]
    assert decision.source == "fallback"
    assert decision.value == SAFE_DEFAULTS["cost-sensitive"]
    errors = " ".join(audit_records(cfg)[-1]["validation"]["errors"])
    assert error in errors


def test_budget_is_enforced(cfg: AIConfig) -> None:
    proposal = copy.deepcopy(SAFE_DEFAULTS["balanced"])
    decision = propose("normal", "x", cfg, Budget(cpu_millicores=100, memory_mi=100), FakeLLM(proposal))  # type: ignore[arg-type]
    assert decision.source == "fallback"
    assert "exceed budget" in " ".join(audit_records(cfg)[-1]["validation"]["errors"])


def test_helm_values_are_chart_compatible(cfg: AIConfig, tmp_path: Path) -> None:
    decision = propose("high availability", "production", cfg, Budget(1500, 1536), FakeLLM(ready=False))  # type: ignore[arg-type]
    text = to_helm_values(decision, "production", "high availability")
    assert "[AI FALLBACK]" in text
    values = yaml.safe_load(text)
    assert set(values) == {"backend", "frontend", "topologySpread"}
    assert values["topologySpread"] == {"enabled": True}
    assert values["backend"]["replicaCount"] == 2
