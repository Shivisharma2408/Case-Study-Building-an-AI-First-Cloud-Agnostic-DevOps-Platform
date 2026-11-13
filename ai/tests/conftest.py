from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aiops.config import AIConfig
from aiops.llm import LLMResponse, LLMUnavailableError


class FakeLLM:
    """Stands in for OllamaClient. `reply` may be a dict (JSON-encoded), a raw str, or an exception."""

    def __init__(self, reply: Any = None, *, ready: bool = True) -> None:
        self.reply = reply
        self.ready = ready
        self.prompts: list[str] = []
        self.model = "fake-model"

    def ensure_ready(self) -> None:
        if not self.ready:
            raise LLMUnavailableError("Ollama not reachable (fake)")

    def generate_json(self, system: str, prompt: str, schema: dict[str, Any]) -> LLMResponse:
        self.prompts.append(prompt)
        if isinstance(self.reply, Exception):
            raise self.reply
        text = self.reply if isinstance(self.reply, str) else json.dumps(self.reply)
        return LLMResponse(text=text, model=self.model, duration_ms=1.0)


@pytest.fixture
def cfg(tmp_path: Path) -> AIConfig:
    return AIConfig(enabled=True, host="http://fake", model="fake-model", timeout_seconds=1, artifacts_dir=tmp_path)


def audit_records(cfg: AIConfig) -> list[dict[str, Any]]:
    index = cfg.audit_dir / "audit.jsonl"
    if not index.exists():
        return []
    return [json.loads(line) for line in index.read_text(encoding="utf-8").splitlines()]
