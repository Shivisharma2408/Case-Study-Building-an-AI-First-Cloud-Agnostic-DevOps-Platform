from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AIConfig:
    enabled: bool
    host: str
    model: str
    timeout_seconds: float
    artifacts_dir: Path

    @property
    def audit_dir(self) -> Path:
        return self.artifacts_dir / "ai"

    @classmethod
    def from_env(cls) -> AIConfig:
        return cls(
            enabled=_env_bool("AI_ENABLED", True),
            host=os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/"),
            model=os.environ.get("OLLAMA_MODEL", "llama3.2:3b"),
            timeout_seconds=float(os.environ.get("AI_TIMEOUT_SECONDS", "90")),
            artifacts_dir=Path(os.environ.get("ARTIFACTS_DIR", str(REPO_ROOT / "artifacts"))),
        )
