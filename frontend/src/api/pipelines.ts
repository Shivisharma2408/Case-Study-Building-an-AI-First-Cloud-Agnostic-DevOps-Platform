import type { PipelineRun, RunSummary } from "../types/pipeline";

/**
 * Typed client for the read-only pipelines API (backend/app/pipelines.py).
 * With VITE_USE_FIXTURES=true it serves src/fixtures instead, so the UI can be
 * developed and tested without running the pipeline or the backend.
 */
export interface PipelinesApi {
  listRuns(signal?: AbortSignal): Promise<RunSummary[]>;
  getRun(runId: string, signal?: AbortSignal): Promise<PipelineRun>;
  getJobLog(runId: string, job: string, signal?: AbortSignal): Promise<string>;
  decide(runId: string, decision: "approve" | "reject", comment?: string): Promise<PipelineRun>;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function errorMessage(resp: Response): Promise<string> {
  try {
    const body: unknown = await resp.json();
    if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // ignore: fall back to the status line
  }
  return `Request failed with status ${resp.status}`;
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  const resp = await fetch(path, { ...init, headers: { Accept: "application/json", ...init?.headers } });
  if (!resp.ok) throw new ApiError(await errorMessage(resp), resp.status);
  return resp;
}

const enc = encodeURIComponent;

export const httpApi: PipelinesApi = {
  async listRuns(signal) {
    return (await (await request("/api/pipelines", { signal })).json()) as RunSummary[];
  },
  async getRun(runId, signal) {
    return (await (await request(`/api/pipelines/${enc(runId)}`, { signal })).json()) as PipelineRun;
  },
  async getJobLog(runId, job, signal) {
    const resp = await request(`/api/pipelines/${enc(runId)}/logs/${enc(job)}`, {
      signal,
      headers: { Accept: "text/plain" },
    });
    return resp.text();
  },
  async decide(runId, decision, comment) {
    const resp = await request(`/api/pipelines/${enc(runId)}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, comment }),
    });
    return (await resp.json()) as PipelineRun;
  },
};

/** Fixture mode is decided at build time, so production bundles never contain the fixtures. */
function lazyFixtureApi(): PipelinesApi {
  const load = () => import("../fixtures/fixtureApi").then((m) => m.fixtureApi);
  return {
    listRuns: (signal) => load().then((api) => api.listRuns(signal)),
    getRun: (runId, signal) => load().then((api) => api.getRun(runId, signal)),
    getJobLog: (runId, job, signal) => load().then((api) => api.getJobLog(runId, job, signal)),
    decide: (runId, decision, comment) => load().then((api) => api.decide(runId, decision, comment)),
  };
}

export const pipelinesApi: PipelinesApi = import.meta.env.VITE_USE_FIXTURES === "true" ? lazyFixtureApi() : httpApi;
