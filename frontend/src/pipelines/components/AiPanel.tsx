import type { AiArtifact } from "../../types/pipeline";

const KIND_LABELS: Record<string, string> = {
  "helm-values": "Environment configuration (Helm values)",
  "deploy-plan": "Deployment plan (command generation)",
  "health-summary": "Health analysis",
  "iac-sizing": "Generative IaC sizing",
};

export function AiPanel({ artifacts }: { artifacts: AiArtifact[] }) {
  const failed = artifacts.filter((a) => a.validation.passed === false).length;
  return (
    <details className="pl-ai-panel" open data-testid="ai-panel">
      <summary>
        <span className="pl-ai-title">AI decisions</span>
        <span className="pl-muted">
          {artifacts.length} artifact{artifacts.length === 1 ? "" : "s"}
          {failed > 0 && ` · ${failed} rejected by validation`}
        </span>
      </summary>
      {artifacts.length === 0 ? (
        <p className="pl-muted pl-pad">No AI steps ran in this run (yet).</p>
      ) : (
        <ul className="pl-ai-list">
          {artifacts.map((a, i) => (
            <AiArtifactCard key={a.id ?? `${a.kind}-${i}`} artifact={a} />
          ))}
        </ul>
      )}
    </details>
  );
}

function ValidationBadge({ passed }: { passed: boolean | null }) {
  if (passed === true) return <span className="pl-chip tone-green">Validation passed</span>;
  if (passed === false) return <span className="pl-chip tone-red">Validation failed</span>;
  return <span className="pl-chip tone-grey">Not validated (no LLM output)</span>;
}

function AiArtifactCard({ artifact: a }: { artifact: AiArtifact }) {
  const rejected = a.validation.passed === false;
  return (
    <li className={`pl-ai-card${rejected ? " is-rejected" : ""}`} data-testid={`ai-${a.kind}`}>
      <div className="pl-ai-card-head">
        <span className="pl-ai-kind" title={a.feature}>
          {a.kind}
        </span>
        <span className="pl-muted">{KIND_LABELS[a.kind] ?? a.feature}</span>
        {a.stage && <span className="pl-chip">{a.stage}</span>}
        <span className="pl-spacer" />
        {a.source === "fallback" ? (
          <span className="pl-chip tone-amber" title={a.fallbackReason ?? undefined}>
            deterministic fallback
          </span>
        ) : (
          <span className="pl-chip tone-blue">LLM · {a.model}</span>
        )}
        <ValidationBadge passed={a.validation.passed} />
      </div>

      {rejected && a.validation.errors.length > 0 && (
        <div className="pl-ai-errors" role="note">
          <strong>LLM output rejected:</strong>
          <ul>
            {a.validation.errors.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
      )}
      {a.source === "fallback" && a.fallbackReason && !rejected && (
        <p className="pl-muted pl-ai-reason">{a.fallbackReason}</p>
      )}

      <div className="pl-ai-output">
        <AiOutput kind={a.kind} output={a.output} />
      </div>

      {a.prompt && (
        <details className="pl-ai-prompt">
          <summary>Prompt{a.rawOutput ? " and raw LLM output" : ""}</summary>
          <pre className="pl-pre">{a.prompt}</pre>
          {a.rawOutput && <pre className="pl-pre">{a.rawOutput}</pre>}
        </details>
      )}
    </li>
  );
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function AiOutput({ kind, output }: { kind: string; output: unknown }) {
  if (kind === "deploy-plan" && Array.isArray(output)) {
    return (
      <ol className="pl-plan">
        {output.map((step, i) => {
          const s = isRecord(step) ? step : {};
          const argv = Array.isArray(s.argv) ? s.argv.map(String) : [];
          return (
            <li key={i}>
              <span>{String(s.description ?? "")}</span>
              <code className="pl-mono">{argv.join(" ")}</code>
            </li>
          );
        })}
      </ol>
    );
  }
  if (kind === "health-summary" && isRecord(output)) {
    return (
      <div className="pl-health">
        <p>
          <span className={`pl-chip ${output.healthy ? "tone-green" : "tone-red"}`}>
            {output.healthy ? "Healthy" : "Unhealthy"}
          </span>{" "}
          {typeof output.confidence === "number" && (
            <span className="pl-muted">confidence {Math.round(output.confidence * 100)}%</span>
          )}{" "}
          {typeof output.recommended_action === "string" && (
            <span className="pl-muted">· action: {output.recommended_action}</span>
          )}
        </p>
        <p>{String(output.summary ?? "")}</p>
        {typeof output.suspected_cause === "string" && output.suspected_cause && (
          <p>
            <strong>Suspected cause:</strong> {output.suspected_cause}
          </p>
        )}
      </div>
    );
  }
  if (kind === "helm-values" && isRecord(output)) {
    const { profile, rationale, ...values } = output;
    return (
      <div>
        <p>
          <span className="pl-chip tone-blue">{String(profile ?? "profile")}</span>{" "}
          <span className="pl-muted">{String(rationale ?? "")}</span>
        </p>
        {Object.keys(values).length > 0 && <pre className="pl-pre">{JSON.stringify(values, null, 2)}</pre>}
      </div>
    );
  }
  return <pre className="pl-pre">{JSON.stringify(output, null, 2)}</pre>;
}
