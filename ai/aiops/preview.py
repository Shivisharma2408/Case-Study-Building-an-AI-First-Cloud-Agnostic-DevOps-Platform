"""AI-assisted command generation for preview environments.

Trigger: a branch name ``deploy-preview/<name>`` or a PR comment
``/deploy-preview <name> [free-text request]`` / ``/destroy-preview <name>``.

Trusted code derives the namespace/release/host from the trigger; the LLM only
proposes the *steps* (as argv lists), which must pass ``commands.validate_plan``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from .commands import (
    PREVIEW_DESTROY_POLICY,
    PREVIEW_POLICY,
    Command,
    CommandPolicy,
    validate_plan,
)
from .config import AIConfig
from .llm import AIDecision, OllamaClient, ValidationFailedError, decide, schema_errors

CHART = "deploy/helm/idea-board"
PREVIEW_VALUES = "deploy/helm/idea-board/values-preview.yaml"

PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["steps"],
    "properties": {
        "steps": {
            "type": "array",
            "minItems": 1,
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["description", "argv"],
                "properties": {
                    "description": {"type": "string", "maxLength": 200},
                    "argv": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 40,
                        "items": {"type": "string", "minLength": 1, "maxLength": 256},
                    },
                },
            },
        }
    },
}

_BRANCH_RE = re.compile(r"^(?:refs/heads/)?deploy-preview/(?P<name>[^\s]+)$")
_COMMENT_RE = re.compile(r"^/(?P<verb>deploy|destroy)-preview\s+(?P<name>\S+)\s*(?P<rest>.*)$", re.S)


@dataclass(frozen=True)
class PreviewRequest:
    action: Literal["deploy", "destroy"]
    name: str
    namespace: str
    release: str
    host: str
    image_tag: str
    instructions: str  # free text after the name in a PR comment (may be empty)

    @property
    def policy(self) -> CommandPolicy:
        return PREVIEW_POLICY if self.action == "deploy" else PREVIEW_DESTROY_POLICY


def slugify(raw: str, max_len: int = 30) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", raw.lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")[:max_len].strip("-")
    if not slug:
        raise ValueError(f"cannot derive a preview name from {raw!r}")
    return slug


def parse_trigger(trigger: str, image_tag: str, base_domain: str = "preview.ideaboard.localhost") -> PreviewRequest:
    text = trigger.strip()
    if m := _BRANCH_RE.match(text):
        action, name, rest = "deploy", m["name"], ""
    elif m := _COMMENT_RE.match(text):
        action, name, rest = m["verb"], m["name"], m["rest"].strip()
    else:
        raise ValueError(
            "trigger must be a branch 'deploy-preview/<name>' or a comment "
            "'/deploy-preview <name> [request]' / '/destroy-preview <name>'"
        )
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", image_tag):
        raise ValueError(f"invalid image tag {image_tag!r}")
    slug = slugify(name)
    return PreviewRequest(
        action=action,  # type: ignore[arg-type]
        name=slug,
        namespace=f"preview-{slug}",
        release=f"idea-board-{slug}",
        host=f"{slug}.{base_domain}",
        image_tag=image_tag,
        instructions=rest[:500],
    )


def deterministic_plan(req: PreviewRequest) -> list[Command]:
    ns = ["-n", req.namespace]
    if req.action == "destroy":
        return [
            Command(("helm", "uninstall", req.release, *ns, "--wait"), "Remove the preview release"),
            Command(("kubectl", "delete", "namespace", req.namespace), "Delete the preview namespace"),
        ]
    return [
        Command(
            (
                "helm",
                "upgrade",
                "--install",
                req.release,
                CHART,
                *ns,
                "--create-namespace",
                "-f",
                PREVIEW_VALUES,
                "--set",
                f"ingress.host={req.host}",
                "--set",
                f"backend.image.tag={req.image_tag}",
                "--set",
                f"frontend.image.tag={req.image_tag}",
                "--wait",
                "--timeout",
                "5m",
            ),
            "Install or upgrade the self-contained preview release",
        ),
        Command(
            ("kubectl", "rollout", "status", f"deployment/{req.release}-backend", *ns, "--timeout=120s"),
            "Wait for the backend rollout",
        ),
        Command(("kubectl", "get", "pods,ingress", *ns, "-o", "wide"), "Show what was deployed"),
    ]


SYSTEM_PROMPT = """You are a deployment planner for a Kubernetes platform.
You output ONLY JSON matching the given schema: {"steps":[{"description":..., "argv":[...]}]}.
Each argv is a command split into arguments - never a shell string, no pipes, no quotes, no variables.
Allowed binaries: kubectl, helm. Never pass --kube-context/--context/--kubeconfig (they are injected).
Every command must target exactly the given namespace with -n <namespace>.
Never read or print Secrets. Keep plans short (2-5 steps)."""


def _prompt(req: PreviewRequest) -> str:
    example = [{"description": c.description, "argv": list(c.argv)} for c in deterministic_plan(req)]
    allowed_sets = sorted(req.policy.set_keys)
    return (
        f"Action: {req.action} preview environment '{req.name}'.\n"
        f"Namespace: {req.namespace}\nHelm release: {req.release}\nChart: {CHART}\n"
        f"Values file: {PREVIEW_VALUES}\nIngress host: {req.host}\nImage tag: {req.image_tag}\n"
        f"Allowed --set keys: {', '.join(allowed_sets)}\n"
        f"Developer request (may be empty): {req.instructions or '(none)'}\n\n"
        "A known-good baseline plan is below. Adapt it ONLY as needed to satisfy the developer "
        "request (e.g. replica counts, log level); otherwise return it unchanged.\n"
        f"{json.dumps({'steps': example})}"
    )


def _parse_plan(req: PreviewRequest) -> Any:
    def parse(data: Any) -> list[Command]:
        errors = schema_errors(data, PLAN_SCHEMA)
        if errors:
            raise ValidationFailedError(errors)
        commands = [Command(tuple(s["argv"]), s["description"]) for s in data["steps"]]
        errors = validate_plan(commands, req.policy, req.namespace)
        # Plan-level invariants: the plan must actually do the requested thing.
        verbs = [c.argv[:2] for c in commands]
        if req.action == "deploy" and ("helm", "upgrade") not in verbs:
            errors.append("deploy plan must contain 'helm upgrade --install'")
        if req.action == "destroy" and ("helm", "uninstall") not in verbs:
            errors.append("destroy plan must contain 'helm uninstall'")
        if req.action == "deploy":
            for c in commands:
                if c.argv[:2] == ("helm", "upgrade"):
                    sets = {a for a in c.argv if "=" in a}
                    for required in (f"backend.image.tag={req.image_tag}", f"frontend.image.tag={req.image_tag}"):
                        if required not in sets:
                            errors.append(f"helm upgrade must pin '{required}'")
        if errors:
            raise ValidationFailedError(errors)
        return commands

    return parse


def plan_preview(
    req: PreviewRequest, config: AIConfig, client: OllamaClient | None = None
) -> AIDecision[list[Command]]:
    return decide(
        feature=f"preview-plan-{req.action}",
        system=SYSTEM_PROMPT,
        prompt=_prompt(req),
        schema=PLAN_SCHEMA,
        parse=_parse_plan(req),
        fallback=lambda: deterministic_plan(req),
        config=config,
        client=client,
        context={"namespace": req.namespace, "release": req.release, "trigger_name": req.name},
        summarize=lambda cmds: [{"description": c.description, "argv": list(c.argv)} for c in cmds],
    )
