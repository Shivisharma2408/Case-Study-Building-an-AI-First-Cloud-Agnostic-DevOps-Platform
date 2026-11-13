"""Audit trail for every AI-assisted decision (published as a pipeline artifact)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

Source = Literal["llm", "fallback"]


@dataclass
class AuditRecord:
    feature: str
    source: Source
    model: str | None
    prompt: str | None
    raw_output: str | None
    validation: dict[str, Any]
    decision: Any
    fallback_reason: str | None = None
    duration_ms: float | None = None
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class AuditLog:
    """Writes one JSON file per decision plus an append-only JSONL index."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def write(self, record: AuditRecord) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        slug = re.sub(r"[^a-z0-9-]+", "-", record.feature.lower()).strip("-")
        path = self.directory / f"{stamp}-{slug}.json"
        payload = asdict(record)
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        with (self.directory / "audit.jsonl").open("a", encoding="utf-8") as index:
            index.write(json.dumps({**payload, "file": path.name}, default=str) + "\n")
        return path
