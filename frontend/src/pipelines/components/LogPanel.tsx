import { useEffect, useRef, useState } from "react";
import { pipelinesApi } from "../../api/pipelines";
import type { Job } from "../../types/pipeline";
import { formatDuration } from "../format";
import { usePolled } from "../hooks";
import { isActive } from "../status";
import { StatusIcon } from "./StatusIcon";

interface Props {
  runId: string;
  stage: string;
  job: Job;
  onClose: () => void;
}

/** Right-side log viewer: monospace, polls + auto-scrolls while the job runs, copy button. */
export function LogPanel({ runId, stage, job, onClose }: Props) {
  const log = usePolled(
    `${runId}/${job.name}`,
    (signal) => pipelinesApi.getJobLog(runId, job.name, signal),
    () => isActive(job.status),
  );
  const preRef = useRef<HTMLPreElement>(null);
  const [follow, setFollow] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const el = preRef.current;
    if (el && follow) el.scrollTop = el.scrollHeight;
  }, [log.data, follow]);

  function onScroll() {
    const el = preRef.current;
    if (el) setFollow(el.scrollHeight - el.scrollTop - el.clientHeight < 24);
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(log.data ?? "");
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <aside className="pl-log-panel" aria-label={`Log for ${job.name}`} data-testid="log-panel">
      <header className="pl-log-header">
        <StatusIcon status={job.status} />
        <div className="pl-log-title">
          <strong>{job.name}</strong>
          <span className="pl-muted">
            {stage}
            {job.durationSec != null && ` · ${formatDuration(job.durationSec)}`}
            {isActive(job.status) && " · live"}
          </span>
        </div>
        <button type="button" className="pl-btn pl-btn--small" onClick={() => void copy()} disabled={!log.data}>
          {copied ? "Copied" : "Copy"}
        </button>
        <button type="button" className="pl-btn pl-btn--icon" onClick={onClose} aria-label="Close log">
          ✕
        </button>
      </header>
      {log.error && (
        <p role="alert" className="pl-error-text">
          Could not load log: {log.error}
        </p>
      )}
      <pre ref={preRef} className="pl-log-text" onScroll={onScroll} data-testid="log-text">
        {log.data == null && !log.error ? "Loading…" : log.data || "(no output yet)"}
      </pre>
    </aside>
  );
}
