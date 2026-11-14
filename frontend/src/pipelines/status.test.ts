import { describe, expect, it } from "vitest";
import { RUN_STATUSES } from "../types/pipeline";
import { formatDuration, timeAgo } from "./format";
import { isActive, STATUS_STYLES, statusColor, statusStyle } from "./status";

describe("status → colour mapping", () => {
  it.each([
    ["succeeded", "green", "#107c10"],
    ["failed", "red", "#c50f1f"],
    ["skipped", "grey", "#8a8886"],
    ["pending", "grey", "#8a8886"],
    ["running", "blue", "#0f6cbd"],
    ["waitingApproval", "amber", "#b76e00"],
    ["rolledBack", "orange", "#c5530c"],
  ] as const)("%s is %s", (status, tone, color) => {
    expect(statusStyle(status).tone).toBe(tone);
    expect(statusColor(status)).toBe(color);
  });

  it("covers every status in the run.json contract", () => {
    expect(Object.keys(STATUS_STYLES).sort()).toEqual([...RUN_STATUSES].sort());
  });

  it("falls back safely for unknown values", () => {
    expect(statusStyle("exploded").label).toBe("Unknown");
    expect(statusColor(undefined)).toBe("#8a8886");
  });

  it("only running and waitingApproval keep polling alive", () => {
    expect(RUN_STATUSES.filter(isActive)).toEqual(["running", "waitingApproval"]);
  });
});

describe("formatting", () => {
  it("formats durations like the Azure DevOps run view", () => {
    expect(formatDuration(null)).toBe("");
    expect(formatDuration(7)).toBe("7s");
    expect(formatDuration(194)).toBe("3m 14s");
    expect(formatDuration(3720)).toBe("1h 2m");
  });

  it("formats relative times", () => {
    const now = Date.parse("2026-11-14T12:00:00Z");
    expect(timeAgo("2026-11-14T11:59:30Z", now)).toBe("just now");
    expect(timeAgo("2026-11-14T11:15:00Z", now)).toBe("45m ago");
    expect(timeAgo("2026-11-14T09:00:00Z", now)).toBe("3h ago");
    expect(timeAgo("2026-11-12T12:00:00Z", now)).toBe("2d ago");
  });
});
