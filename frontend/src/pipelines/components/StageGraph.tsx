import { Fragment, useState } from "react";
import type { Approval, Job, PipelineRun, Stage } from "../../types/pipeline";
import { formatDuration, secondsBetween } from "../format";
import { statusStyle } from "../status";
import { StatusIcon } from "./StatusIcon";

export interface JobRef {
  stage: string;
  job: string;
}

interface StageGraphProps {
  run: PipelineRun;
  expanded: ReadonlySet<string>;
  onToggleStage: (stage: string) => void;
  selectedJob: JobRef | null;
  onSelectJob: (ref: JobRef) => void;
  onDecide?: (decision: "approve" | "reject", comment: string) => Promise<void>;
  now?: number;
}

/** Horizontal, left-to-right stage cards connected by arrows (Azure DevOps run view). */
export function StageGraph({ run, expanded, onToggleStage, selectedJob, onSelectJob, onDecide, now }: StageGraphProps) {
  return (
    <ol className="pl-stage-graph" aria-label="Stages">
      {run.stages.map((stage, i) => (
        <Fragment key={stage.name}>
          {i > 0 && (
            <li className={`pl-stage-arrow tone-${statusStyle(run.stages[i - 1]?.status).tone}`} aria-hidden="true">
              <svg viewBox="0 0 40 12" width="24" height="12" preserveAspectRatio="none">
                <line x1="0" y1="6" x2="32" y2="6" />
                <polygon points="32,1 40,6 32,11" />
              </svg>
            </li>
          )}
          <li className="pl-stage-slot">
            <StageCard
              stage={stage}
              expanded={expanded.has(stage.name)}
              onToggle={() => onToggleStage(stage.name)}
              selectedJob={selectedJob}
              onSelectJob={onSelectJob}
              approval={run.approval?.stage === stage.name ? run.approval : null}
              onDecide={onDecide}
              now={now}
            />
          </li>
        </Fragment>
      ))}
    </ol>
  );
}

interface StageCardProps {
  stage: Stage;
  expanded: boolean;
  onToggle: () => void;
  selectedJob: JobRef | null;
  onSelectJob: (ref: JobRef) => void;
  approval: Approval | null;
  onDecide?: StageGraphProps["onDecide"];
  now?: number;
}

export function StageCard({ stage, expanded, onToggle, selectedJob, onSelectJob, approval, onDecide, now }: StageCardProps) {
  const s = statusStyle(stage.status);
  const duration = formatDuration(secondsBetween(stage.startedAt, stage.finishedAt, now));
  const jobsId = `jobs-${stage.name}`;
  return (
    <section className={`pl-stage-card tone-${s.tone}`} data-testid={`stage-${stage.name}`} data-status={stage.status}>
      <button
        type="button"
        className="pl-stage-head"
        onClick={onToggle}
        aria-expanded={expanded}
        aria-controls={jobsId}
      >
        <StatusIcon status={stage.status} size="lg" />
        <span className="pl-stage-title">
          <span className="pl-stage-name">{stage.name}</span>
          <span className="pl-stage-meta">
            {s.label}
            {duration && ` · ${duration}`}
            {` · ${stage.jobs.length} job${stage.jobs.length === 1 ? "" : "s"}`}
          </span>
        </span>
        <span className="pl-chevron" aria-hidden="true">
          {expanded ? "▾" : "▸"}
        </span>
      </button>

      {stage.status === "waitingApproval" && approval && onDecide && <ApprovalGate onDecide={onDecide} />}
      {approval?.decision && (
        <p className={`pl-approval-note ${approval.decision === "approved" ? "tone-green" : "tone-red"}`}>
          {approval.decision === "approved" ? "Approved" : approval.decision === "rejected" ? "Rejected" : "Timed out"}
          {approval.decidedBy && ` by ${approval.decidedBy}`}
          {approval.comment && ` — “${approval.comment}”`}
        </p>
      )}

      {expanded && (
        <ul className="pl-jobs" id={jobsId}>
          {stage.jobs.map((job) => (
            <JobRow
              key={job.name}
              job={job}
              selected={selectedJob?.stage === stage.name && selectedJob.job === job.name}
              onSelect={() => onSelectJob({ stage: stage.name, job: job.name })}
              now={now}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

interface JobRowProps {
  job: Job;
  selected: boolean;
  onSelect: () => void;
  now?: number;
}

export function JobRow({ job, selected, onSelect, now }: JobRowProps) {
  const seconds = job.durationSec ?? secondsBetween(job.startedAt, job.finishedAt, now);
  const startable = job.status !== "pending" && job.status !== "skipped";
  return (
    <li>
      <button
        type="button"
        className={`pl-job-row${selected ? " is-selected" : ""}`}
        onClick={onSelect}
        disabled={!startable}
        data-testid={`job-${job.name}`}
        data-status={job.status}
        title={startable ? "Show log" : statusStyle(job.status).label}
      >
        <StatusIcon status={job.status} size="sm" />
        <span className="pl-job-name">{job.name}</span>
        <span className="pl-job-duration">{formatDuration(seconds)}</span>
      </button>
    </li>
  );
}

function ApprovalGate({ onDecide }: { onDecide: NonNullable<StageGraphProps["onDecide"]> }) {
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function decide(decision: "approve" | "reject") {
    setBusy(true);
    setError(null);
    try {
      await onDecide(decision, comment.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="pl-approval" data-testid="approval-gate">
      <p className="pl-approval-title">Approval required to deploy to production</p>
      <input
        type="text"
        className="pl-input"
        placeholder="Comment (optional)"
        value={comment}
        maxLength={500}
        onChange={(e) => setComment(e.target.value)}
        aria-label="Approval comment"
      />
      <div className="pl-approval-actions">
        <button type="button" className="pl-btn pl-btn--primary" disabled={busy} onClick={() => void decide("approve")}>
          Approve
        </button>
        <button type="button" className="pl-btn" disabled={busy} onClick={() => void decide("reject")}>
          Reject
        </button>
      </div>
      {error && (
        <p role="alert" className="pl-error-text">
          {error}
        </p>
      )}
    </div>
  );
}
