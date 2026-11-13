"""Generative IaC: a small service spec -> Helm values + Terraform landing-zone stub.

The LLM never writes HCL or YAML. It proposes *numbers* (replicas, resources, probe
timings) as schema-constrained JSON; trusted templates render the files. The rendered
files are then gated by `helm lint` and `terraform validate` (scripts/stages/generate_iac.sh)
before they are accepted into services/<name>/.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import yaml

from .config import SCHEMA_DIR, AIConfig
from .llm import AIDecision, OllamaClient, ValidationFailedError, decide, schema_errors

SPEC_SCHEMA: dict[str, Any] = json.loads((SCHEMA_DIR / "service-spec.schema.json").read_text(encoding="utf-8"))

SIZING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "replicaCount",
        "cpu_request",
        "cpu_limit",
        "memory_request",
        "memory_limit",
        "readiness_period_seconds",
        "liveness_initial_delay_seconds",
        "rationale",
    ],
    "properties": {
        "replicaCount": {"type": "integer", "minimum": 1, "maximum": 4},
        "cpu_request": {"type": "string", "pattern": "^[1-9][0-9]{0,3}m$"},
        "cpu_limit": {"type": "string", "pattern": "^[1-9][0-9]{0,3}m$"},
        "memory_request": {"type": "string", "pattern": "^[1-9][0-9]{0,4}Mi$"},
        "memory_limit": {"type": "string", "pattern": "^[1-9][0-9]{0,4}Mi$"},
        "readiness_period_seconds": {"type": "integer", "minimum": 2, "maximum": 30},
        "liveness_initial_delay_seconds": {"type": "integer", "minimum": 0, "maximum": 120},
        "rationale": {"type": "string", "minLength": 1, "maxLength": 400},
    },
}

_TIER_DEFAULTS: dict[str, dict[str, Any]] = {
    "low": {
        "replicaCount": 1,
        "cpu_request": "25m",
        "cpu_limit": "200m",
        "memory_request": "64Mi",
        "memory_limit": "128Mi",
        "readiness_period_seconds": 10,
        "liveness_initial_delay_seconds": 10,
        "rationale": "Deterministic sizing for low traffic.",
    },
    "medium": {
        "replicaCount": 2,
        "cpu_request": "100m",
        "cpu_limit": "500m",
        "memory_request": "128Mi",
        "memory_limit": "256Mi",
        "readiness_period_seconds": 5,
        "liveness_initial_delay_seconds": 10,
        "rationale": "Deterministic sizing for medium traffic.",
    },
    "high": {
        "replicaCount": 3,
        "cpu_request": "250m",
        "cpu_limit": "1000m",
        "memory_request": "256Mi",
        "memory_limit": "512Mi",
        "readiness_period_seconds": 5,
        "liveness_initial_delay_seconds": 15,
        "rationale": "Deterministic sizing for high traffic.",
    },
}


def load_spec(path: Path) -> dict[str, Any]:
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    errors = schema_errors(spec, SPEC_SCHEMA)
    if errors:
        raise ValueError(f"invalid service spec {path}: " + "; ".join(errors))
    spec.setdefault("health_path", "/healthz")
    spec.setdefault("public", False)
    spec.setdefault("expected_traffic", "low")
    if spec["public"] and "host" not in spec:
        spec["host"] = f"{spec['name']}.ideaboard.localhost"
    return spec


def _sizing_errors(s: dict[str, Any]) -> list[str]:
    errors = schema_errors(s, SIZING_SCHEMA)
    if errors:
        return errors
    if int(s["cpu_request"][:-1]) > int(s["cpu_limit"][:-1]):
        errors.append("cpu_request exceeds cpu_limit")
    if int(s["memory_request"][:-2]) > int(s["memory_limit"][:-2]):
        errors.append("memory_request exceeds memory_limit")
    return errors


def propose_sizing(
    spec: dict[str, Any], config: AIConfig, client: OllamaClient | None = None
) -> AIDecision[dict[str, Any]]:
    def parse(data: Any) -> dict[str, Any]:
        errors = _sizing_errors(data)
        if errors:
            raise ValidationFailedError(errors)
        return data

    reference = _TIER_DEFAULTS[spec["expected_traffic"]]
    return decide(
        feature=f"geniac-{spec['name']}",
        system="You size Kubernetes workloads. Output ONLY JSON matching the schema. Be frugal; "
        "requests must not exceed limits.",
        prompt=f"Service spec:\n{json.dumps(spec)}\nReference sizing for its traffic tier:\n{json.dumps(reference)}",
        schema=SIZING_SCHEMA,
        parse=parse,
        fallback=lambda: copy.deepcopy(reference),
        config=config,
        client=client,
        context={"service": spec["name"]},
    )


def render_values(spec: dict[str, Any], sizing: dict[str, Any]) -> dict[str, Any]:
    repository, _, tag = spec["image"].rpartition(":")
    return {
        "name": spec["name"],
        "image": {"repository": repository, "tag": tag},
        "port": spec["port"],
        "replicaCount": sizing["replicaCount"],
        "resources": {
            "requests": {"cpu": sizing["cpu_request"], "memory": sizing["memory_request"]},
            "limits": {"cpu": sizing["cpu_limit"], "memory": sizing["memory_limit"]},
        },
        "probes": {
            "path": spec["health_path"],
            "readinessPeriodSeconds": sizing["readiness_period_seconds"],
            "livenessInitialDelaySeconds": sizing["liveness_initial_delay_seconds"],
        },
        "ingress": {
            "enabled": bool(spec["public"]),
            "host": spec.get("host", ""),
            "pathPrefix": spec.get("path_prefix", "/"),
        },
    }


def _quota(sizing: dict[str, Any]) -> dict[str, str]:
    # Headroom for one surge pod during rolling updates.
    n = sizing["replicaCount"] + 1
    return {
        "requests_cpu": f"{n * int(sizing['cpu_request'][:-1])}m",
        "requests_memory": f"{n * int(sizing['memory_request'][:-2])}Mi",
        "limits_cpu": f"{n * int(sizing['cpu_limit'][:-1])}m",
        "limits_memory": f"{n * int(sizing['memory_limit'][:-2])}Mi",
        "pods": str(n + 2),
    }


def render_terraform(spec: dict[str, Any], sizing: dict[str, Any]) -> str:
    q = _quota(sizing)
    return f"""# Generated by aiops geniac for service '{spec["name"]}'. Regenerate rather than edit.
# Landing zone (namespace, quota, limits) via the shared, cloud-agnostic app module.
terraform {{
  required_version = ">= 1.6.0"
  required_providers {{
    kubernetes = {{ source = "hashicorp/kubernetes", version = "~> 2.35" }}
  }}
}}

variable "kubeconfig_path" {{
  type    = string
  default = "~/.kube/config"
}}

variable "kube_context" {{
  type    = string
  default = "kind-idea-board"
}}

provider "kubernetes" {{
  config_path    = pathexpand(var.kubeconfig_path)
  config_context = var.kube_context
}}

module "landing_zone" {{
  source    = "../../../infra/terraform/modules/app"
  namespace = "{spec["name"]}"
  quota = {{
    requests_cpu    = "{q["requests_cpu"]}"
    requests_memory = "{q["requests_memory"]}"
    limits_cpu      = "{q["limits_cpu"]}"
    limits_memory   = "{q["limits_memory"]}"
    pods            = {q["pods"]}
  }}
}}
"""


def generate(
    spec_path: Path,
    out_dir: Path,
    config: AIConfig,
    client: OllamaClient | None = None,
    suffix: str = ".candidate",
) -> tuple[Path, AIDecision[dict[str, Any]]]:
    """Render into out_dir/<name><suffix>. Candidates sit at the same depth as accepted
    services so relative module paths validate identically; the gate script renames them."""
    spec = load_spec(spec_path)
    decision = propose_sizing(spec, config, client)
    target = out_dir / f"{spec['name']}{suffix}"
    (target / "helm").mkdir(parents=True, exist_ok=True)
    (target / "terraform").mkdir(parents=True, exist_ok=True)
    header = (
        f"# Generated by aiops geniac from {spec_path.name}. {decision.banner}\n"
        f"# Sizing rationale: {decision.value['rationale']}\n"
    )
    (target / "helm" / "values.yaml").write_text(
        header + yaml.safe_dump(render_values(spec, decision.value), sort_keys=False), encoding="utf-8"
    )
    (target / "terraform" / "main.tf").write_text(render_terraform(spec, decision.value), encoding="utf-8")
    return target, decision
