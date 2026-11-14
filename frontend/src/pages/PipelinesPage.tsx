import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { pipelinesApi } from "../api/pipelines";
import { AiPanel } from "../pipelines/components/AiPanel";
import { LogPanel } from "../pipelines/components/LogPanel";
import { RollbackBanner, RunHeader } from "../pipelines/components/RunHeader";
import { RunSidebar } from "../pipelines/components/RunSidebar";
import { type JobRef, StageGraph } from "../pipelines/components/StageGraph";
import { useNow, usePolled } from "../pipelines/hooks";
import { isActive } from "../pipelines/status";
import type { PipelineRun } from "../types/pipeline";
import "../pipelines/pipelines.css";

/** Stages worth showing open by default: anything not plainly finished. */
function defaultExpanded(run: PipelineRun): Set<string> {
  return new Set(
    run.stages
      .filter((s) => s.status !== "succeeded" && s.status !== "skipped" && s.status !== "pending")
      .map((s) => s.name),
  );
}

export default function PipelinesPage() {
  const [params, setParams] = useSearchParams();
  const runs = usePolled(
    "runs",
    (signal) => pipelinesApi.listRuns(signal),
    (data) => data?.some((r) => isActive(r.status)) ?? false,
  );

  const selectedId = params.get("run") ?? runs.data?.[0]?.runId ?? null;
  const run = usePolled(
    selectedId,
    (signal) => pipelinesApi.getRun(selectedId ?? "", signal),
    (data) => isActive(data?.status),
  );
  const now = useNow(isActive(run.data?.status));

  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selectedJob, setSelectedJob] = useState<JobRef | null>(null);
  const loadedRunId = run.data?.runId;

  // New run selected: reset the view (open interesting stages, close the log).
  useEffect(() => {
    setSelectedJob(null);
    if (run.data) setExpanded(defaultExpanded(run.data));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only when the run identity changes
  }, [loadedRunId]);

  const toggleStage = useCallback((name: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }, []);

  const decide = useCallback(
    async (decision: "approve" | "reject", comment: string) => {
      if (!selectedId) return;
      run.setData(await pipelinesApi.decide(selectedId, decision, comment || undefined));
      runs.reload();
    },
    [selectedId, run, runs],
  );

  const job = useMemo(() => {
    if (!selectedJob || !run.data) return null;
    return (
      run.data.stages.find((s) => s.name === selectedJob.stage)?.jobs.find((j) => j.name === selectedJob.job) ?? null
    );
  }, [selectedJob, run.data]);

  if (runs.error && !runs.data) {
    return (
      <div className="pl-page pl-centered">
        <div className="pl-state pl-state--error" role="alert">
          <h2>Could not load pipeline runs</h2>
          <p>{runs.error}</p>
          <button type="button" className="pl-btn" onClick={runs.reload}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!runs.data) {
    return (
      <div className="pl-page pl-centered">
        <p className="pl-muted">Loading pipeline runs…</p>
      </div>
    );
  }

  if (runs.data.length === 0) {
    return (
      <div className="pl-page pl-centered">
        <div className="pl-state" data-testid="empty-state">
          <h2>No pipeline runs yet</h2>
          <p>Start one from a terminal in the repository (Git Bash):</p>
          <pre className="pl-pre">bash scripts/pipeline.sh simulate</pre>
          <p className="pl-muted">
            or <code>bash scripts/pipeline.sh lint-test</code> for a real stage. This page refreshes automatically.
          </p>
          <button type="button" className="pl-btn" onClick={runs.reload}>
            Refresh
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`pl-page${job ? " has-log" : ""}`}>
      <RunSidebar runs={runs.data} selectedId={selectedId} onSelect={(id) => setParams({ run: id })} now={now} />
      <main className="pl-main">
        {run.error && !run.data && (
          <div className="pl-banner tone-red" role="alert">
            Could not load run {selectedId}: {run.error}
          </div>
        )}
        {!run.data && !run.error && <p className="pl-muted pl-pad">Loading run…</p>}
        {run.data && (
          <>
            <RunHeader run={run.data} now={now} />
            <RollbackBanner run={run.data} />
            {run.error && (
              <div className="pl-banner tone-amber" role="status">
                Live refresh failed ({run.error}); showing the last known state.
              </div>
            )}
            <section className="pl-section" aria-label="Stages">
              <h2 className="pl-section-title">Stages</h2>
              <StageGraph
                run={run.data}
                expanded={expanded}
                onToggleStage={toggleStage}
                selectedJob={selectedJob}
                onSelectJob={setSelectedJob}
                onDecide={decide}
                now={now}
              />
            </section>
            <section className="pl-section">
              <AiPanel artifacts={run.data.aiArtifacts} />
            </section>
          </>
        )}
      </main>
      {job && selectedJob && run.data && (
        <LogPanel runId={run.data.runId} stage={selectedJob.stage} job={job} onClose={() => setSelectedJob(null)} />
      )}
    </div>
  );
}
