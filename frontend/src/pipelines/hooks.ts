import { useCallback, useEffect, useRef, useState } from "react";

export interface Polled<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
  setData: (value: T) => void;
}

/**
 * Loads `load()` whenever `key` changes and re-polls every `intervalMs` while
 * `shouldPoll(data)` is true. Stops automatically once the data says "done".
 */
export function usePolled<T>(
  key: string | null,
  load: (signal: AbortSignal) => Promise<T>,
  shouldPoll: (data: T | null) => boolean,
  intervalMs = 3000,
): Polled<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tick, setTick] = useState(0);
  const loadRef = useRef(load);
  loadRef.current = load;

  useEffect(() => {
    setData(null);
    setError(null);
  }, [key]);

  useEffect(() => {
    if (key == null) return;
    const controller = new AbortController();
    setLoading(true);
    loadRef
      .current(controller.signal)
      .then((value) => {
        setData(value);
        setError(null);
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [key, tick]);

  const polling = key != null && shouldPoll(data);
  useEffect(() => {
    if (!polling) return;
    const id = window.setInterval(() => setTick((t) => t + 1), intervalMs);
    return () => window.clearInterval(id);
  }, [polling, intervalMs]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload, setData };
}

/** Current time, re-rendering every second while `active` (live durations). */
export function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [active]);
  return now;
}
