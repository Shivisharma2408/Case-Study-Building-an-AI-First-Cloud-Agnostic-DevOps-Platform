from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path
from typing import Any

import pytest
import yaml

from aiops.config import REPO_ROOT, AIConfig
from aiops.geniac import generate, load_spec
from aiops.llm import LLMUnavailableError, OllamaClient
from tests.conftest import FakeLLM, audit_records


class FakeResponse(io.BytesIO):
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def opener_returning(payloads: dict[str, Any]):  # type: ignore[no-untyped-def]
    def _open(req, timeout):  # type: ignore[no-untyped-def]
        for suffix, payload in payloads.items():
            if req.full_url.endswith(suffix):
                if isinstance(payload, Exception):
                    raise payload
                return FakeResponse(json.dumps(payload).encode())
        raise AssertionError(req.full_url)

    return _open


def test_ollama_client_happy_path() -> None:
    client = OllamaClient(
        "http://ollama:11434",
        "llama3.2:3b",
        5,
        opener=opener_returning(
            {
                "/api/tags": {"models": [{"name": "llama3.2:3b"}]},
                "/api/generate": {"response": '{"ok": true}'},
            }
        ),
    )
    client.ensure_ready()
    assert json.loads(client.generate_json("s", "p", {"type": "object"}).text) == {"ok": True}


def test_ollama_client_missing_model() -> None:
    client = OllamaClient(
        "http://o",
        "qwen2.5-coder:3b",
        5,
        opener=opener_returning(
            {
                "/api/tags": {"models": [{"name": "llama3.2:3b"}]},
            }
        ),
    )
    with pytest.raises(LLMUnavailableError, match="ollama pull qwen2.5-coder:3b"):
        client.ensure_ready()


def test_ollama_client_unreachable() -> None:
    client = OllamaClient(
        "http://o",
        "m",
        5,
        opener=opener_returning(
            {
                "/api/tags": urllib.error.URLError("connection refused"),
            }
        ),
    )
    with pytest.raises(LLMUnavailableError, match="not reachable"):
        client.ensure_ready()


def test_load_example_spec() -> None:
    spec = load_spec(REPO_ROOT / "ai/examples/notifications.service.yaml")
    assert spec["name"] == "notifications" and spec["public"] is False


def test_invalid_spec_is_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: Bad_Name\ndescription: x\nimage: nope\nport: 80\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid service spec"):
        load_spec(bad)


def test_geniac_fallback_renders_files(cfg: AIConfig, tmp_path: Path) -> None:
    target, decision = generate(
        REPO_ROOT / "ai/examples/notifications.service.yaml", tmp_path, cfg, FakeLLM(ready=False)
    )  # type: ignore[arg-type]
    assert decision.source == "fallback"
    assert target.name == "notifications.candidate"
    values = yaml.safe_load((target / "helm/values.yaml").read_text(encoding="utf-8"))
    assert values["image"] == {"repository": "nginxinc/nginx-unprivileged", "tag": "1.27.3-alpine3.20"}
    assert values["ingress"]["enabled"] is False
    tf = (target / "terraform/main.tf").read_text(encoding="utf-8")
    assert 'namespace = "notifications"' in tf and "../../../infra/terraform/modules/app" in tf


def test_geniac_rejects_inconsistent_llm_sizing(cfg: AIConfig, tmp_path: Path) -> None:
    sizing = {
        "replicaCount": 2,
        "cpu_request": "500m",
        "cpu_limit": "100m",
        "memory_request": "64Mi",
        "memory_limit": "128Mi",
        "readiness_period_seconds": 5,
        "liveness_initial_delay_seconds": 5,
        "rationale": "x",
    }
    _, decision = generate(REPO_ROOT / "ai/examples/notifications.service.yaml", tmp_path, cfg, FakeLLM(sizing))  # type: ignore[arg-type]
    assert decision.source == "fallback"
    assert "cpu_request exceeds cpu_limit" in audit_records(cfg)[-1]["validation"]["errors"]
