"""Ollama client and the single, audited "ask the LLM or fall back" code path."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, TypeVar

import jsonschema

from .audit import AuditLog, AuditRecord, Source
from .config import AIConfig

T = TypeVar("T")


class LLMUnavailableError(RuntimeError):
    """The LLM cannot be used right now (not running, model missing, timeout...)."""


class ValidationFailedError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    duration_ms: float


Opener = Callable[..., Any]


class OllamaClient:
    """Minimal Ollama HTTP client (stdlib only). Uses structured outputs (format=<JSON schema>)."""

    def __init__(self, host: str, model: str, timeout_seconds: float, opener: Opener | None = None) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout_seconds
        self._open = opener or urllib.request.urlopen

    def _request(self, path: str, body: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(  # noqa: S310 - host comes from operator config
            f"{self.host}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST" if body is not None else "GET",
        )
        try:
            with self._open(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            raise LLMUnavailableError(f"Ollama not reachable at {self.host}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise LLMUnavailableError(f"Ollama returned non-JSON: {exc}") from exc

    def ensure_ready(self) -> None:
        tags = self._request("/api/tags", None, timeout=3)
        names = {m.get("name", "") for m in tags.get("models", [])}
        wanted = {self.model, f"{self.model}:latest"}
        if not names & wanted:
            raise LLMUnavailableError(f"model '{self.model}' is not pulled (run: ollama pull {self.model})")

    def generate_json(self, system: str, prompt: str, schema: dict[str, Any]) -> LLMResponse:
        start = time.perf_counter()
        body = {
            "model": self.model,
            "system": system,
            "prompt": prompt,
            "format": schema,
            "stream": False,
            "options": {"temperature": 0, "seed": 7},
        }
        result = self._request("/api/generate", body, timeout=self.timeout)
        text = result.get("response")
        if not isinstance(text, str) or not text.strip():
            raise LLMUnavailableError("Ollama returned an empty response")
        return LLMResponse(text=text, model=self.model, duration_ms=(time.perf_counter() - start) * 1000)


def schema_errors(instance: Any, schema: dict[str, Any]) -> list[str]:
    validator = jsonschema.Draft7Validator(schema)
    errors = []
    for err in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path)):
        where = "/".join(str(p) for p in err.absolute_path) or "<root>"
        errors.append(f"{where}: {err.message}")
    return errors


@dataclass(frozen=True)
class AIDecision(Generic[T]):
    value: T
    source: Source
    model: str | None
    fallback_reason: str | None
    audit_path: Path | None

    @property
    def banner(self) -> str:
        if self.source == "llm":
            return f"[AI] decision produced by local LLM '{self.model}' and passed validation."
        return f"[AI FALLBACK] deterministic logic used - {self.fallback_reason}"


def decide(
    *,
    feature: str,
    system: str,
    prompt: str,
    schema: dict[str, Any],
    parse: Callable[[Any], T],
    fallback: Callable[[], T],
    config: AIConfig,
    client: OllamaClient | None = None,
    context: dict[str, Any] | None = None,
    summarize: Callable[[T], Any] | None = None,
) -> AIDecision[T]:
    """Ask the LLM for schema-constrained JSON; validate it with ``parse``; else ``fallback()``.

    ``parse`` must raise :class:`ValidationFailedError` for anything unacceptable.
    Never raises because the LLM misbehaved: the pipeline must not break on AI.
    """
    audit = AuditLog(config.audit_dir)
    summarize = summarize or (lambda v: v)
    raw: str | None = None
    model: str | None = None
    duration: float | None = None
    validation: dict[str, Any] = {"valid": False, "errors": []}

    reason: str
    if not config.enabled:
        reason = "AI disabled (AI_ENABLED=false)"
    else:
        client = client or OllamaClient(config.host, config.model, config.timeout_seconds)
        try:
            client.ensure_ready()
            response = client.generate_json(system, prompt, schema)
            raw, model, duration = response.text, response.model, response.duration_ms
            try:
                parsed_json = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValidationFailedError([f"output is not valid JSON: {exc}"]) from exc
            value = parse(parsed_json)
            validation = {"valid": True, "errors": []}
            path = audit.write(
                AuditRecord(
                    feature=feature,
                    source="llm",
                    model=model,
                    prompt=f"{system}\n\n{prompt}",
                    raw_output=raw,
                    validation=validation,
                    decision=summarize(value),
                    duration_ms=duration,
                    context=context or {},
                )
            )
            return AIDecision(value, "llm", model, None, path)
        except LLMUnavailableError as exc:
            reason = f"LLM unavailable: {exc}"
        except ValidationFailedError as exc:
            validation = {"valid": False, "errors": exc.errors}
            reason = f"LLM output rejected by validation: {exc}"
        except Exception as exc:  # defensive: AI must never break the pipeline
            reason = f"unexpected AI error: {type(exc).__name__}: {exc}"

    value = fallback()
    path = audit.write(
        AuditRecord(
            feature=feature,
            source="fallback",
            model=model or config.model,
            prompt=f"{system}\n\n{prompt}",
            raw_output=raw,
            validation=validation,
            decision=summarize(value),
            fallback_reason=reason,
            duration_ms=duration,
            context=context or {},
        )
    )
    return AIDecision(value, "fallback", model, reason, path)
