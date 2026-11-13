"""CLI: python -m aiops <command> ... (see `python -m aiops --help`)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import envconfig, geniac, health, preview
from .commands import execute
from .config import AIConfig
from .llm import LLMUnavailableError, OllamaClient


def _cmd_status(cfg: AIConfig, _: argparse.Namespace) -> int:
    if not cfg.enabled:
        print("AI disabled (AI_ENABLED=false): all features use deterministic fallbacks.")
        return 0
    try:
        OllamaClient(cfg.host, cfg.model, cfg.timeout_seconds).ensure_ready()
        print(f"Ollama ready at {cfg.host} with model '{cfg.model}'.")
    except LLMUnavailableError as exc:
        print(f"Ollama not usable ({exc}). AI features will use deterministic fallbacks.")
    return 0  # informational only: never fails the pipeline


def _cmd_preview(cfg: AIConfig, a: argparse.Namespace) -> int:
    req = preview.parse_trigger(a.trigger, a.image_tag)
    decision = preview.plan_preview(req, cfg)
    print(decision.banner)
    print(f"preview: action={req.action} namespace={req.namespace} release={req.release} host={req.host}")
    for i, cmd in enumerate(decision.value, 1):
        print(f"  {i}. {cmd.description}\n     {cmd}")
    print(f"audit: {decision.audit_path}")
    if not a.execute:
        return 0
    results = execute(decision.value, req.policy, req.namespace, a.context, dry_run=a.dry_run)
    failed = [r for r in results if r.returncode != 0]
    if not failed and req.action == "deploy":
        print(f"preview ready: http://{req.host}:{a.ingress_port}/")
    return 1 if failed else 0


def _cmd_env_config(cfg: AIConfig, a: argparse.Namespace) -> int:
    spec = Path(a.spec_file).read_text(encoding="utf-8")
    budget = envconfig.Budget(cpu_millicores=a.cpu_budget, memory_mi=a.memory_budget)
    decision = envconfig.propose(spec, a.environment, cfg, budget)
    out = envconfig.write_values(decision, a.environment, spec, Path(a.out))
    print(decision.banner)
    print(f"profile: {decision.value['profile']} -> {out}")
    print(f"audit: {decision.audit_path}")
    return 0


def _cmd_health(cfg: AIConfig, a: argparse.Namespace) -> int:
    report = health.run_health_gate(
        namespace=a.namespace,
        release=a.release,
        context=a.context,
        base_url=a.base_url,
        host=a.host,
        config=cfg,
        deploy_failed=a.deploy_failed,
        auto_rollback=not a.no_rollback,
        settle_seconds=a.settle,
    )
    return report.exit_code


def _cmd_geniac(cfg: AIConfig, a: argparse.Namespace) -> int:
    target, decision = geniac.generate(Path(a.spec), Path(a.out), cfg)
    print(decision.banner)
    print(json.dumps({"candidate_dir": str(target), "audit": str(decision.audit_path)}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aiops", description="Local-LLM assisted DevOps tooling")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="report whether the local LLM is usable")

    p = sub.add_parser("preview", help="plan (and optionally run) a preview deploy/destroy")
    p.add_argument("--trigger", required=True, help="branch name or PR comment")
    p.add_argument("--image-tag", required=True)
    p.add_argument("--context", default="kind-idea-board")
    p.add_argument("--ingress-port", default="8080")
    p.add_argument("--execute", action="store_true", help="run the validated plan")
    p.add_argument("--dry-run", action="store_true")

    e = sub.add_parser("env-config", help="goal text -> validated Helm values")
    e.add_argument("--environment", required=True)
    e.add_argument("--spec-file", required=True)
    e.add_argument("--out", required=True)
    e.add_argument("--cpu-budget", type=int, default=1000, help="millicores")
    e.add_argument("--memory-budget", type=int, default=1024, help="Mi")

    h = sub.add_parser("health", help="post-deploy health gate with automatic rollback")
    h.add_argument("--namespace", required=True)
    h.add_argument("--release", required=True)
    h.add_argument("--context", default="kind-idea-board")
    h.add_argument("--base-url")
    h.add_argument("--host")
    h.add_argument("--deploy-failed", action="store_true")
    h.add_argument("--no-rollback", action="store_true")
    h.add_argument("--settle", type=int, default=0)

    g = sub.add_parser("geniac", help="service spec -> Helm values + Terraform stub (candidate)")
    g.add_argument("--spec", required=True)
    g.add_argument("--out", default="services")

    args = parser.parse_args(argv)
    cfg = AIConfig.from_env()
    handlers = {
        "status": _cmd_status,
        "preview": _cmd_preview,
        "env-config": _cmd_env_config,
        "health": _cmd_health,
        "geniac": _cmd_geniac,
    }
    return handlers[args.command](cfg, args)


if __name__ == "__main__":
    sys.exit(main())
