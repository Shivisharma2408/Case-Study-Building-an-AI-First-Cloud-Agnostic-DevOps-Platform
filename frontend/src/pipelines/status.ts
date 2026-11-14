import type { RunStatus } from "../types/pipeline";

export interface StatusStyle {
  /** Semantic colour token, also used as a CSS modifier: .status--green etc. */
  tone: "green" | "red" | "grey" | "blue" | "amber" | "orange";
  /** Hex colour for inline SVG / tests. */
  color: string;
  label: string;
  /** Single glyph rendered inside the status circle. */
  glyph: string;
  /** Still in progress: drives polling and the spinning icon. */
  active: boolean;
}

export const STATUS_STYLES: Record<RunStatus, StatusStyle> = {
  succeeded: { tone: "green", color: "#107c10", label: "Succeeded", glyph: "✓", active: false },
  failed: { tone: "red", color: "#c50f1f", label: "Failed", glyph: "✕", active: false },
  skipped: { tone: "grey", color: "#8a8886", label: "Skipped", glyph: "–", active: false },
  pending: { tone: "grey", color: "#8a8886", label: "Not started", glyph: "○", active: false },
  running: { tone: "blue", color: "#0f6cbd", label: "Running", glyph: "↻", active: true },
  waitingApproval: { tone: "amber", color: "#b76e00", label: "Waiting for approval", glyph: "‖", active: true },
  rolledBack: { tone: "orange", color: "#c5530c", label: "Rolled back", glyph: "↺", active: false },
};

const UNKNOWN: StatusStyle = { tone: "grey", color: "#8a8886", label: "Unknown", glyph: "?", active: false };

export function statusStyle(status: string | null | undefined): StatusStyle {
  return (status && STATUS_STYLES[status as RunStatus]) || UNKNOWN;
}

export function statusColor(status: string | null | undefined): string {
  return statusStyle(status).color;
}

/** Polling is needed while anything can still change. */
export function isActive(status: string | null | undefined): boolean {
  return statusStyle(status).active;
}
