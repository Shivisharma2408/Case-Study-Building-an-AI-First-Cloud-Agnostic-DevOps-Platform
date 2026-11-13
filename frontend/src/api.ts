export interface Idea {
  id: number;
  content: string;
  created_at: string;
}

export const MAX_IDEA_LENGTH = 500;

async function parseError(resp: Response): Promise<string> {
  try {
    const body: unknown = await resp.json();
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail) && detail.length > 0) {
        const first: unknown = detail[0];
        if (first && typeof first === "object" && "msg" in first) {
          return String((first as { msg: unknown }).msg);
        }
      }
    }
  } catch {
    // fall through to the generic message
  }
  return `Request failed with status ${resp.status}`;
}

export async function fetchIdeas(signal?: AbortSignal): Promise<Idea[]> {
  const resp = await fetch("/api/ideas", { signal, headers: { Accept: "application/json" } });
  if (!resp.ok) throw new Error(await parseError(resp));
  return (await resp.json()) as Idea[];
}

export async function createIdea(content: string): Promise<Idea> {
  const resp = await fetch("/api/ideas", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!resp.ok) throw new Error(await parseError(resp));
  return (await resp.json()) as Idea;
}
