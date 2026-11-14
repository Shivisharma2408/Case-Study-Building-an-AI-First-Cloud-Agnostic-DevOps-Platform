import type { RunSummary } from "../../types/pipeline";
import { timeAgo } from "../format";
import { statusStyle } from "../status";

interface Props {
  runs: RunSummary[];
  selectedId: string | null;
  onSelect: (runId: string) => void;
  now?: number;
}

export function RunSidebar({ runs, selectedId, onSelect, now }: Props) {
  return (
    <nav className="pl-sidebar" aria-label="Recent runs">
      <h2 className="pl-sidebar-title">Runs</h2>
      <ul>
        {runs.map((run) => {
          const s = statusStyle(run.status);
          return (
            <li key={run.runId}>
              <button
                type="button"
                className={`pl-run-item${run.runId === selectedId ? " is-selected" : ""}`}
                onClick={() => onSelect(run.runId)}
                aria-current={run.runId === selectedId ? "true" : undefined}
                data-testid={`run-item-${run.runId}`}
              >
                <span className={`pl-dot tone-${s.tone}${s.active ? " is-active" : ""}`} title={s.label} />
                <span className="pl-run-item-body">
                  <span className="pl-run-item-title">#{run.runNumber}</span>
                  <span className="pl-run-item-meta">
                    <span className="pl-branch" title={run.branch}>
                      {run.branch}
                    </span>
                    <span>{timeAgo(run.startedAt, now)}</span>
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
