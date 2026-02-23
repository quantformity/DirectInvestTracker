import { useState, useEffect, useRef } from "react";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const POLL_MS   = 500;
const TIMEOUT_MS = 90_000;

export interface BackendState {
  ready: boolean;
  elapsed: number;   // seconds since first poll — used to progressively update the message
  timedOut: boolean;
}

export function useBackendReady(): BackendState {
  const [ready, setReady]       = useState(false);
  const [elapsed, setElapsed]   = useState(0);
  const [timedOut, setTimedOut] = useState(false);

  const stoppedRef = useRef(false);
  const startRef   = useRef(Date.now());

  useEffect(() => {
    stoppedRef.current = false;
    startRef.current   = Date.now();

    // Tick elapsed counter every second for progressive status messages
    const ticker = setInterval(() => {
      if (!stoppedRef.current) {
        setElapsed(Math.floor((Date.now() - startRef.current) / 1000));
      }
    }, 1000);

    const poll = async () => {
      if (stoppedRef.current) return;

      if (Date.now() - startRef.current > TIMEOUT_MS) {
        setTimedOut(true);
        return;
      }

      try {
        const res = await fetch(`${BASE_URL}/`, {
          signal: AbortSignal.timeout(2000),
        });
        if (res.ok) {
          if (!stoppedRef.current) setReady(true);
          return;
        }
      } catch {
        // backend not ready yet — schedule next poll
      }

      setTimeout(poll, POLL_MS);
    };

    poll();

    return () => {
      stoppedRef.current = true;
      clearInterval(ticker);
    };
  }, []);

  return { ready, elapsed, timedOut };
}
