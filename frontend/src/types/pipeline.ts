/** Contract of artifacts/runs/<runId>/run.json (written by scripts/runstate.py). */

export const RUN_STATUSES = [
  "pending",
  "running",
  "succeeded",
  "failed",
  "skipped",
  "rolledBack",
  "waitingApproval",
] as const;

export type RunStatus = (typeof RUN_STATUSES)[number];

export type Trigger = "manual" | "branch" | "pr-comment" | "pr" | "ci";

export interface Job {
  name: string;
  status: RunStatus;
  startedAt: string | null;
  finishedAt: string | null;
  durationSec: number | null;
  /** Relative to the run directory, e.g. "logs/build.log". */
  logPath: string;
}

export interface Stage {
  name: string;
  status: RunStatus;
  startedAt: string | null;
  finishedAt: string | null;
  jobs: Job[];
}

export interface Approval {
  stage: string;
  decision: "approved" | "rejected" | "timedOut" | null;
  requestedAt?: string | null;
  decidedAt: string | null;
  decidedBy: string | null;
  comment: string | null;
}

export interface AiValidation {
  /** true = LLM output accepted, false = rejected, null = no LLM output to validate. */
  passed: boolean | null;
  errors: string[];
}

export interface AiArtifact {
  id?: string | null;
  kind: string;
  feature?: string;
  stage: string | null;
  source: "llm" | "fallback";
  model: string | null;
  prompt: string | null;
  rawOutput?: string | null;
  output: unknown;
  validation: AiValidation;
  fallbackReason: string | null;
  timestamp: string;
}

export interface Incident {
  summary: string;
  report: string | null;
}

export interface PipelineRun {
  schemaVersion: number;
  runId: string;
  runNumber: string;
  pipeline: string;
  branch: string;
  commit: string;
  commitMessage?: string;
  trigger: Trigger | string;
  triggerDetail?: string;
  startedAt: string;
  finishedAt: string | null;
  status: RunStatus;
  stages: Stage[];
  approval: Approval | null;
  aiArtifacts: AiArtifact[];
  incident: Incident | null;
}

export type RunSummary = Pick<
  PipelineRun,
  "runId" | "runNumber" | "pipeline" | "branch" | "commit" | "trigger" | "status" | "startedAt" | "finishedAt"
>;
