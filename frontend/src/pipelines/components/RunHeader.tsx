import type { PipelineRun } from "../../types/pipeline";
import { formatDuration, secondsBetween, triggerLabel } from "../format";
import { StatusBadge } from "./StatusIcon";

export function RunHeader({ run, now }: { run: PipelineRun; now?: number }) {
  const duration = formatDuration(secondsBetween(run.startedAt, run.finishedAt, now));
  return (
    <header className="pl-run-header">
      <div className="pl-run-header-top">
        <span className="pl-pipeline-name">{run.pipeline}</span>
        <h1 className="pl-run-title">#{run.runNumber}</h1>
        <StatusBadge status={run.status} />
      </div>
      {run.commitMessage && <p className="pl-commit-message">{run.commitMessage}</p>}
      <dl className="pl-run-facts">
        <div>
          <dt>Branch</dt>
          <dd className="pl-mono">{run.branch}</dd>
        </div>
        <div>
          <dt>Commit</dt>
          <dd className="pl-mono" title={run.commit}>
            {run.commit.slice(0, 7)}
          </dd>
        </div>
        <div>
          <dt>Trigger</dt>
          <dd title={run.triggerDetail}>
            {triggerLabel(run.trigger)}
            {run.triggerDetail && <span className="pl-muted"> · {run.triggerDetail}</span>}
          </dd>
        </div>
        <div>
          <dt>Started</dt>
          <dd>{new Date(run.startedAt).toLocaleString()}</dd>
        </div>
        <div>
          <dt>Duration</dt>
          <dd data-testid="run-duration">{duration || "—"}</dd>
        </div>
      </dl>
    </header>
  );
}

export function RollbackBanner({ run }: { run: PipelineRun }) {
  if (run.status !== "rolledBack" && !run.incident) return null;
  return (
    <div className="pl-banner tone-orange" role="alert" data-testid="rollback-banner">
      <strong>Release rolled back automatically by the AI health gate.</strong>
      <p>{run.incident?.summary ?? "The health gate detected an unhealthy release and rolled it back."}</p>
      {run.incident?.report && (
        <details>
          <summary>Incident report</summary>
          <pre className="pl-pre">{run.incident.report}</pre>
        </details>
      )}
    </div>
  );
}
