export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds) || seconds < 0) return "";
  const s = Math.round(seconds);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${s % 60}s`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

export function secondsBetween(start: string | null | undefined, end: string | null | undefined, now = Date.now()): number | null {
  if (!start) return null;
  const a = Date.parse(start);
  const b = end ? Date.parse(end) : now;
  return Number.isNaN(a) || Number.isNaN(b) ? null : Math.max(0, (b - a) / 1000);
}

export function timeAgo(iso: string | null | undefined, now = Date.now()): string {
  const s = secondsBetween(iso, null, now);
  if (s == null) return "";
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export const TRIGGER_LABELS: Record<string, string> = {
  manual: "Manually triggered",
  branch: "Branch trigger",
  "pr-comment": "PR comment",
  pr: "Pull request",
  ci: "Continuous integration",
};

export function triggerLabel(trigger: string): string {
  return TRIGGER_LABELS[trigger] ?? trigger;
}
