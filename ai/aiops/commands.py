"""Allowlist validation and safe execution of (possibly AI-generated) kubectl/helm commands.

Threat model: the LLM output is untrusted input. A command is only executed if it is
an argv list (never a shell string) that passes every rule below; the kube context is
injected by the executor and can never come from the plan.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

# Anything that could matter to a shell, a glob, or a YAML/JSON injection is rejected outright.
_FORBIDDEN_CHARS = re.compile(r"[;&|`$<>\\\"'*?(){}\[\]!#~\s]")
_SAFE_SET_VALUE = re.compile(r"^[A-Za-z0-9._:/-]{1,128}$")
_DNS_LABEL = re.compile(r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$")

_GLOBAL_FORBIDDEN_FLAGS = {
    "--kubeconfig",
    "--context",
    "--kube-context",
    "--cluster",
    "--user",
    "--token",
    "--server",
    "-s",
    "--as",
    "--as-group",
    "--as-uid",
    "--insecure-skip-tls-verify",
    "--all-namespaces",
    "-A",
    "--post-renderer",
    "--repo",
    "--set-file",
    "--set-string",
    "--set-json",
    "--set-literal",
    "--force",
    "--grace-period",
    "--raw",
    "--username",
    "--password",
    "--certificate-authority",
    "--client-key",
    "--client-certificate",
}

_HELM_VALUE_FLAGS = {"-n", "--namespace", "-f", "--values", "--set", "--timeout", "--max", "-o", "--output"}
_HELM_BOOL_FLAGS = {"--install", "--wait", "--atomic", "--create-namespace", "--cleanup-on-fail", "--wait-for-jobs"}
_KUBECTL_VALUE_FLAGS = {
    "-n",
    "--namespace",
    "--timeout",
    "-o",
    "--output",
    "-l",
    "--selector",
    "--tail",
    "-c",
    "--container",
}
_KUBECTL_BOOL_FLAGS = {"--previous", "--all-containers", "--wait"}

_KUBECTL_READ_RESOURCES = {
    "pods",
    "pod",
    "po",
    "deployments",
    "deployment",
    "deploy",
    "services",
    "service",
    "svc",
    "ingress",
    "ingresses",
    "ing",
    "events",
    "event",
    "replicasets",
    "rs",
    "hpa",
    "horizontalpodautoscalers",
    "pdb",
    "poddisruptionbudgets",
    "networkpolicies",
    "netpol",
}


@dataclass(frozen=True)
class Command:
    argv: tuple[str, ...]
    description: str = ""

    def __str__(self) -> str:
        return " ".join(self.argv)


@dataclass(frozen=True)
class CommandPolicy:
    """What a plan is allowed to do. Built by trusted code, never by the LLM."""

    namespace_patterns: tuple[str, ...]
    release_pattern: str = r"^idea-board(-[a-z0-9-]{1,40})?$"
    chart_paths: tuple[str, ...] = ("deploy/helm/idea-board",)
    values_files: tuple[str, ...] = ("deploy/helm/idea-board/values-preview.yaml",)
    set_keys: frozenset[str] = frozenset(
        {
            "backend.image.tag",
            "frontend.image.tag",
            "ingress.host",
            "backend.replicaCount",
            "frontend.replicaCount",
            "backend.logLevel",
        }
    )
    allow_destroy: bool = False  # helm uninstall / kubectl delete namespace
    allow_rollback: bool = False
    allow_install: bool = True

    def namespace_allowed(self, namespace: str) -> bool:
        return bool(_DNS_LABEL.match(namespace)) and any(re.fullmatch(p, namespace) for p in self.namespace_patterns)


PREVIEW_POLICY = CommandPolicy(namespace_patterns=(r"preview-[a-z0-9-]{1,40}",))
PREVIEW_DESTROY_POLICY = CommandPolicy(
    namespace_patterns=(r"preview-[a-z0-9-]{1,40}",), allow_destroy=True, allow_install=False
)
ROLLBACK_POLICY = CommandPolicy(
    namespace_patterns=(r"staging", r"production", r"preview-[a-z0-9-]{1,40}"),
    allow_rollback=True,
    allow_install=False,
)


@dataclass
class _Parsed:
    positionals: list[str] = field(default_factory=list)
    flags: list[tuple[str, str | None]] = field(default_factory=list)

    def values(self, *names: str) -> list[str]:
        return [v for f, v in self.flags if f in names and v is not None]

    def has(self, name: str) -> bool:
        return any(f == name for f, _ in self.flags)


def _parse(args: Sequence[str], value_flags: set[str], bool_flags: set[str]) -> tuple[_Parsed, list[str]]:
    parsed, errors = _Parsed(), []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("-"):
            name, eq, inline = arg.partition("=")
            if name in _GLOBAL_FORBIDDEN_FLAGS:
                errors.append(f"flag '{name}' is forbidden")
            elif name in value_flags:
                if eq:
                    parsed.flags.append((name, inline))
                elif i + 1 < len(args) and not args[i + 1].startswith("-"):
                    parsed.flags.append((name, args[i + 1]))
                    i += 1
                else:
                    errors.append(f"flag '{name}' requires a value")
            elif name in bool_flags and not eq:
                parsed.flags.append((name, None))
            else:
                errors.append(f"flag '{name}' is not allowlisted")
        else:
            parsed.positionals.append(arg)
        i += 1
    return parsed, errors


def _check_namespace(parsed: _Parsed, policy: CommandPolicy, expected: str) -> list[str]:
    namespaces = parsed.values("-n", "--namespace")
    if len(namespaces) != 1:
        return [f"exactly one namespace flag is required (got {len(namespaces)})"]
    ns = namespaces[0]
    errors = []
    if ns != expected:
        errors.append(f"namespace '{ns}' differs from the expected namespace '{expected}'")
    if not policy.namespace_allowed(ns):
        errors.append(f"namespace '{ns}' is not allowlisted")
    return errors


def _validate_helm(args: Sequence[str], policy: CommandPolicy, expected_ns: str) -> list[str]:
    parsed, errors = _parse(args, _HELM_VALUE_FLAGS, _HELM_BOOL_FLAGS)
    if not parsed.positionals:
        return [*errors, "helm subcommand missing"]
    sub, rest = parsed.positionals[0], parsed.positionals[1:]
    errors += _check_namespace(parsed, policy, expected_ns)

    def release_ok(name: str) -> list[str]:
        return [] if re.fullmatch(policy.release_pattern, name) else [f"release '{name}' not allowed"]

    if sub == "upgrade":
        if not policy.allow_install:
            errors.append("installs/upgrades are not permitted by this policy")
        if not parsed.has("--install"):
            errors.append("helm upgrade must use --install")
        if len(rest) != 2:
            return [*errors, "helm upgrade expects <release> <chart>"]
        errors += release_ok(rest[0])
        if rest[1] not in policy.chart_paths:
            errors.append(f"chart '{rest[1]}' is not an allowlisted local chart")
        for vf in parsed.values("-f", "--values"):
            if vf not in policy.values_files:
                errors.append(f"values file '{vf}' is not allowlisted")
        for kv in parsed.values("--set"):
            key, eq, value = kv.partition("=")
            if not eq or "," in kv:
                errors.append(f"--set '{kv}' must be a single key=value")
            elif key not in policy.set_keys:
                errors.append(f"--set key '{key}' is not allowlisted")
            elif not _SAFE_SET_VALUE.match(value):
                errors.append(f"--set value for '{key}' contains unsafe characters")
        if parsed.has("--create-namespace") and not policy.allow_install:
            errors.append("--create-namespace not permitted")
    elif sub in {"status", "history"}:
        if len(rest) != 1:
            errors.append(f"helm {sub} expects <release>")
        else:
            errors += release_ok(rest[0])
    elif sub == "rollback":
        if not policy.allow_rollback:
            errors.append("rollback is not permitted by this policy")
        if len(rest) not in (1, 2) or (len(rest) == 2 and not rest[1].isdigit()):
            errors.append("helm rollback expects <release> [revision]")
        else:
            errors += release_ok(rest[0])
    elif sub == "uninstall":
        if not policy.allow_destroy:
            errors.append("uninstall is not permitted by this policy")
        if len(rest) != 1:
            errors.append("helm uninstall expects <release>")
        else:
            errors += release_ok(rest[0])
    else:
        errors.append(f"helm subcommand '{sub}' is not allowlisted")
    return errors


def _validate_kubectl(args: Sequence[str], policy: CommandPolicy, expected_ns: str) -> list[str]:
    parsed, errors = _parse(args, _KUBECTL_VALUE_FLAGS, _KUBECTL_BOOL_FLAGS)
    if not parsed.positionals:
        return [*errors, "kubectl subcommand missing"]
    sub, rest = parsed.positionals[0], parsed.positionals[1:]

    if any("secret" in a.lower() for a in args):
        errors.append("secrets must never be read by a generated plan")

    if sub == "delete":
        if not policy.allow_destroy:
            errors.append("delete is not permitted by this policy")
        if rest != ["namespace", expected_ns] or parsed.flags:
            errors.append("only 'kubectl delete namespace <expected preview namespace>' is allowed")
        elif not policy.namespace_allowed(expected_ns):
            errors.append(f"namespace '{expected_ns}' is not allowlisted")
        return errors

    errors += _check_namespace(parsed, policy, expected_ns)
    if sub in {"get", "describe"}:
        if not rest:
            errors.append(f"kubectl {sub} expects a resource")
        else:
            kind = rest[0].split("/")[0].lower()
            for part in kind.split(","):
                if part not in _KUBECTL_READ_RESOURCES:
                    errors.append(f"resource '{part}' is not allowlisted for {sub}")
    elif sub == "rollout":
        if len(rest) != 2 or rest[0] != "status" or not rest[1].startswith("deployment/"):
            errors.append("only 'kubectl rollout status deployment/<name>' is allowed")
    elif sub == "logs":
        if len(rest) != 1:
            errors.append("kubectl logs expects exactly one pod/deployment")
    else:
        errors.append(f"kubectl subcommand '{sub}' is not allowlisted")
    return errors


def validate_command(cmd: Command, policy: CommandPolicy, expected_namespace: str) -> list[str]:
    argv = cmd.argv
    if not argv:
        return ["empty command"]
    if len(argv) > 40:
        return ["too many arguments"]
    errors = []
    for arg in argv:
        if not isinstance(arg, str) or not arg or len(arg) > 256:
            errors.append("arguments must be non-empty strings of at most 256 characters")
            break
        if _FORBIDDEN_CHARS.search(arg):
            errors.append(f"argument '{arg[:40]}' contains forbidden characters")
    if errors:
        return errors
    binary, args = argv[0], argv[1:]
    if binary == "helm":
        return _validate_helm(args, policy, expected_namespace)
    if binary == "kubectl":
        return _validate_kubectl(args, policy, expected_namespace)
    return [f"binary '{binary}' is not allowlisted (only kubectl and helm)"]


def validate_plan(commands: Sequence[Command], policy: CommandPolicy, expected_namespace: str) -> list[str]:
    if not commands:
        return ["plan has no steps"]
    if len(commands) > 8:
        return ["plan has more than 8 steps"]
    errors = []
    for i, cmd in enumerate(commands, start=1):
        errors += [f"step {i} ({cmd}): {e}" for e in validate_command(cmd, policy, expected_namespace)]
    return errors


@dataclass
class StepResult:
    command: str
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def _default_runner(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, timeout=900, check=False)


def execute(
    commands: Sequence[Command],
    policy: CommandPolicy,
    expected_namespace: str,
    kube_context: str,
    *,
    dry_run: bool = False,
    runner: Runner | None = None,
    echo: Callable[[str], None] = print,
) -> list[StepResult]:
    """Re-validate and run each step without a shell. Stops at the first failure."""
    errors = validate_plan(commands, policy, expected_namespace)
    if errors:
        raise PermissionError("refusing to execute unvalidated plan: " + "; ".join(errors))
    if not re.fullmatch(r"[A-Za-z0-9_.:@/-]{1,128}", kube_context):
        raise PermissionError("invalid kube context")
    run = runner or _default_runner
    results: list[StepResult] = []
    for cmd in commands:
        ctx_flag = "--kube-context" if cmd.argv[0] == "helm" else "--context"
        argv = [cmd.argv[0], ctx_flag, kube_context, *cmd.argv[1:]]
        echo(f"$ {' '.join(argv)}" + ("   [dry-run]" if dry_run else ""))
        if dry_run:
            results.append(StepResult(" ".join(argv), 0, "", ""))
            continue
        proc = run(argv)
        results.append(StepResult(" ".join(argv), proc.returncode, proc.stdout, proc.stderr))
        if proc.stdout:
            echo(proc.stdout.rstrip())
        if proc.returncode != 0:
            echo(proc.stderr.rstrip())
            break
    return results
