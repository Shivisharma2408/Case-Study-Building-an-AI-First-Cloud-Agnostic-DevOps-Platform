import { statusStyle } from "../status";

interface Props {
  status: string;
  size?: "sm" | "md" | "lg";
}

export function StatusIcon({ status, size = "md" }: Props) {
  const s = statusStyle(status);
  return (
    <span
      className={`pl-status-icon pl-status-icon--${size} tone-${s.tone}${s.active ? " is-active" : ""}`}
      role="img"
      aria-label={s.label}
      title={s.label}
      data-status={status}
    >
      <span aria-hidden="true">{s.glyph}</span>
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const s = statusStyle(status);
  return (
    <span className={`pl-badge tone-${s.tone}`} data-testid="run-status-badge" data-status={status}>
      <StatusIcon status={status} size="sm" />
      {s.label}
    </span>
  );
}
