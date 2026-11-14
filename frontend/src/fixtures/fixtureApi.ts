import type { PipelinesApi } from "../api/pipelines";
import type { PipelineRun, RunSummary } from "../types/pipeline";

/**
 * In-memory implementation of the pipelines API backed by the JSON/log files in this folder.
 * Enabled with VITE_USE_FIXTURES=true (npm run dev:fixtures, Playwright, unit tests).
 */
const runModules = import.meta.glob<PipelineRun>("./runs/*.json", { eager: true, import: "default" });
const logModules = import.meta.glob<string>("./logs/*.log", { eager: true, query: "?raw", import: "default" });

const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

export const fixtureRuns: PipelineRun[] = Object.values(runModules)
  .map(clone)
  .sort((a, b) => b.startedAt.localeCompare(a.startedAt));

const state = new Map(fixtureRuns.map((run) => [run.runId, clone(run)]));

function summary(run: PipelineRun): RunSummary {
  const { runId, runNumber, pipeline, branch, commit, trigger, status, startedAt, finishedAt } = run;
  return { runId, runNumber, pipeline, branch, commit, trigger, status, startedAt, finishedAt };
}

function find(runId: string): PipelineRun {
  const run = state.get(runId);
  if (!run) throw new Error("run not found");
  return run;
}

const delay = () => new Promise((resolve) => setTimeout(resolve, 60));

export const fixtureApi: PipelinesApi = {
  async listRuns() {
    await delay();
    return [...state.values()].sort((a, b) => b.startedAt.localeCompare(a.startedAt)).map(summary);
  },
  async getRun(runId) {
    await delay();
    return clone(find(runId));
  },
  async getJobLog(runId, job) {
    await delay();
    find(runId);
    return logModules[`./logs/${job}.log`] ?? `(fixture) no log recorded for job '${job}'\n`;
  },
  async decide(runId, decision, comment) {
    await delay();
    const run = find(runId);
    if (run.status !== "waitingApproval" || !run.approval) throw new Error("this run is not waiting for approval");
    const now = new Date().toISOString();
    run.approval = { ...run.approval, decision: decision === "approve" ? "approved" : "rejected", decidedAt: now,
      decidedBy: "anonymous (fixtures)", comment: comment ?? null };
    const stage = run.stages.find((s) => s.name === run.approval?.stage);
    if (stage) {
      const ok = decision === "approve";
      stage.status = ok ? "succeeded" : "skipped";
      stage.finishedAt = now;
      stage.jobs = stage.jobs.map((j) => ({ ...j, status: ok ? "succeeded" : "skipped", durationSec: ok ? 20 : null }));
      run.status = ok ? "succeeded" : "failed";
      run.finishedAt = now;
    }
    return clone(run);
  },
};
