"""aiops: local-LLM (Ollama) assisted DevOps tooling with deterministic fallbacks.

Design rules shared by every feature:
  1. The LLM only ever returns JSON constrained by a JSON Schema.
  2. That JSON is validated (schema + semantic policy) before it is used.
  3. Anything that fails validation, or an unavailable LLM, falls back to
     deterministic logic - and the output says so.
  4. Every decision (prompt, model, raw output, validation result, source) is
     written to an audit artifact.
"""

__version__ = "1.0.0"
