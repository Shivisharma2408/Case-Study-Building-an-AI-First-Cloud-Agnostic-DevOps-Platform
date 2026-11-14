import { expect, test } from "@playwright/test";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

interface FixtureRun {
  runId: string;
  startedAt: string;
  stages: { name: string; jobs: { name: string; status: string }[] }[];
}

// The dev server runs in fixture mode, so "latest run" = newest fixture by startedAt.
const fixturesDir = join(process.cwd(), "src", "fixtures", "runs");
const [latest] = readdirSync(fixturesDir)
  .map((f) => JSON.parse(readFileSync(join(fixturesDir, f), "utf-8")) as FixtureRun)
  .sort((a, b) => b.startedAt.localeCompare(a.startedAt));
if (!latest) throw new Error(`no fixture runs in ${fixturesDir}`);

test("pipelines page shows the latest run, its stages and a job log", async ({ page }) => {
  await page.goto("/pipelines");

  for (const stage of latest.stages) {
    await expect(page.getByTestId(`stage-${stage.name}`)).toBeVisible();
    await expect(page.getByTestId(`stage-${stage.name}`).getByText(stage.name, { exact: true })).toBeVisible();
  }

  // expand the first stage and open its first job's log
  const [first] = latest.stages;
  const firstJob = first?.jobs[0];
  if (!first || !firstJob) throw new Error("latest fixture run has no stages/jobs");
  await page.getByTestId(`stage-${first.name}`).getByRole("button").first().click();
  await page.getByTestId(`job-${firstJob.name}`).click();

  const panel = page.getByTestId("log-panel");
  await expect(panel).toBeVisible();
  await expect(panel.getByTestId("log-text")).toContainText(`job ${firstJob.name} started`);
});

test("navigation keeps the Idea Board reachable", async ({ page }) => {
  await page.goto("/pipelines");
  await page.getByRole("link", { name: "Ideas" }).click();
  await expect(page.getByRole("heading", { name: "The Idea Board" })).toBeVisible();
});
