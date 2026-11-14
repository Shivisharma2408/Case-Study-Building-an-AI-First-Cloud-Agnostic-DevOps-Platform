import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import succeededRun from "../fixtures/runs/20261114-091200-c3d4.json";
import rolledBackRun from "../fixtures/runs/20261114-102300-e5f6.json";
import waitingRun from "../fixtures/runs/20261114-113000-a1b2.json";
import type { PipelineRun } from "../types/pipeline";
import { AiPanel } from "./components/AiPanel";
import { RollbackBanner } from "./components/RunHeader";
import { StageGraph } from "./components/StageGraph";

const asRun = (data: unknown) => data as PipelineRun;

afterEach(cleanup);

function renderGraph(run: PipelineRun, expanded: string[] = [], handlers: Partial<Parameters<typeof StageGraph>[0]> = {}) {
  const props = {
    run,
    expanded: new Set(expanded),
    onToggleStage: vi.fn(),
    selectedJob: null,
    onSelectJob: vi.fn(),
    onDecide: vi.fn(async () => undefined),
    ...handlers,
  };
  render(<StageGraph {...props} />);
  return props;
}

describe("StageGraph", () => {
  it("renders every stage from run.json in order with its status", () => {
    const run = asRun(succeededRun);
    renderGraph(run);
    const cards = screen.getAllByTestId(/^stage-/);
    expect(cards.map((c) => c.getAttribute("data-testid"))).toEqual(run.stages.map((s) => `stage-${s.name}`));
    for (const stage of run.stages) {
      const card = screen.getByTestId(`stage-${stage.name}`);
      expect(card.getAttribute("data-status")).toBe(stage.status);
      expect(within(card).getByText(stage.name)).toBeTruthy();
    }
    // durations come from run.json timestamps: lint-test ran 3m 14s
    expect(within(screen.getByTestId("stage-lint-test")).getByText(/3m 14s/)).toBeTruthy();
  });

  it("shows job rows only for expanded stages, with status and duration", () => {
    renderGraph(asRun(succeededRun), ["promote-production"]);
    expect(screen.queryByTestId("job-build")).toBeNull();
    const deploy = screen.getByTestId("job-deploy-production");
    expect(deploy.getAttribute("data-status")).toBe("succeeded");
    expect(within(deploy).getByText("27s")).toBeTruthy();
    expect(screen.getByTestId("job-verify-production")).toBeTruthy();
  });

  it("toggles a stage and selects a job on click", () => {
    const props = renderGraph(asRun(succeededRun), ["build"]);
    fireEvent.click(within(screen.getByTestId("stage-lint-test")).getByRole("button", { expanded: false }));
    expect(props.onToggleStage).toHaveBeenCalledWith("lint-test");
    fireEvent.click(screen.getByTestId("job-build"));
    expect(props.onSelectJob).toHaveBeenCalledWith({ stage: "build", job: "build" });
  });

  it("disables not-started and skipped jobs", () => {
    renderGraph(asRun(rolledBackRun), ["verify-staging"]);
    expect((screen.getByTestId("job-verify-staging") as HTMLButtonElement).disabled).toBe(true);
  });

  it("shows the approval gate and forwards the decision", () => {
    const props = renderGraph(asRun(waitingRun));
    const gate = screen.getByTestId("approval-gate");
    fireEvent.change(within(gate).getByLabelText("Approval comment"), { target: { value: "lgtm" } });
    fireEvent.click(within(gate).getByRole("button", { name: "Approve" }));
    expect(props.onDecide).toHaveBeenCalledWith("approve", "lgtm");
    expect(within(gate).getByRole("button", { name: "Reject" })).toBeTruthy();
  });
});

describe("AI panel and rollback banner", () => {
  it("marks fallback and failed validation", () => {
    render(<AiPanel artifacts={asRun(succeededRun).aiArtifacts} />);
    expect(screen.getAllByText("Validation passed")).toHaveLength(2);
    expect(screen.getByText("Validation failed")).toBeTruthy();
    expect(screen.getByText("deterministic fallback")).toBeTruthy();
    expect(screen.getByText(/high-availability requires at least 2 replicas/)).toBeTruthy();
  });

  it("shows the incident summary for a rolled-back run", () => {
    render(<RollbackBanner run={asRun(rolledBackRun)} />);
    expect(screen.getByTestId("rollback-banner").textContent).toMatch(/ImagePullBackOff/);
  });

  it("shows no banner for a healthy run", () => {
    render(<RollbackBanner run={asRun(succeededRun)} />);
    expect(screen.queryByTestId("rollback-banner")).toBeNull();
  });
});
