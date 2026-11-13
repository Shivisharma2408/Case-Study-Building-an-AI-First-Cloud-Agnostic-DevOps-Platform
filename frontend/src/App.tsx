import { type FormEvent, useCallback, useEffect, useState } from "react";
import { createIdea, fetchIdeas, type Idea, MAX_IDEA_LENGTH } from "./api";

type LoadState = "loading" | "ready" | "error";

const dateFormat = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

export default function App() {
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [draft, setDraft] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoadState("loading");
    try {
      setIdeas(await fetchIdeas(signal));
      setLoadState("ready");
    } catch (err) {
      if (signal?.aborted) return;
      setError(err instanceof Error ? err.message : String(err));
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const trimmed = draft.trim();
  const tooLong = trimmed.length > MAX_IDEA_LENGTH;
  const canSubmit = trimmed.length > 0 && !tooLong && !submitting;

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await createIdea(trimmed);
      setIdeas((prev) => [created, ...prev]);
      setDraft("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="container">
      <header>
        <h1>The Idea Board</h1>
        <p className="subtitle">Share an idea. Everyone can see it.</p>
      </header>

      <form className="card" onSubmit={onSubmit} aria-label="Submit a new idea">
        <label htmlFor="idea">Your idea</label>
        <textarea
          id="idea"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="What if we…"
          rows={3}
          maxLength={MAX_IDEA_LENGTH + 50}
        />
        <div className="form-footer">
          <span className={tooLong ? "counter over" : "counter"}>
            {trimmed.length}/{MAX_IDEA_LENGTH}
          </span>
          <button type="submit" disabled={!canSubmit}>
            {submitting ? "Posting…" : "Post idea"}
          </button>
        </div>
      </form>

      {error && (
        <div role="alert" className="error">
          {error}
        </div>
      )}

      <section aria-live="polite">
        <h2>Ideas {loadState === "ready" && <span className="count">{ideas.length}</span>}</h2>
        {loadState === "loading" && <p className="muted">Loading…</p>}
        {loadState === "error" && (
          <button type="button" className="secondary" onClick={() => void load()}>
            Retry
          </button>
        )}
        {loadState === "ready" && ideas.length === 0 && (
          <p className="muted">No ideas yet — be the first.</p>
        )}
        <ul className="ideas">
          {ideas.map((idea) => (
            <li key={idea.id} className="card">
              <p>{idea.content}</p>
              <time dateTime={idea.created_at}>{dateFormat.format(new Date(idea.created_at))}</time>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
