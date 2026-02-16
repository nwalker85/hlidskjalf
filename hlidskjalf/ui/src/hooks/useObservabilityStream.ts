import { useEffect, useMemo, useRef, useState } from "react";

export type ObservabilityEvent = {
  type: string;
  event_type?: string;
  source?: string;
  target?: string;
  timestamp?: string;
  payload?: Record<string, unknown>;
  message?: string;
};

type StreamStatus = "connecting" | "open" | "closed" | "error";

interface Options {
  enabled?: boolean;
  maxEvents?: number;
}

const STREAM_ENDPOINT = "/api/norns/observability/stream";

export function useObservabilityStream(options: Options = {}) {
  const { enabled = true, maxEvents = 200 } = options;

  const [events, setEvents] = useState<ObservabilityEvent[]>([]);
  const [status, setStatus] = useState<StreamStatus>("connecting");
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!enabled) {
      setStatus("closed");
      return;
    }

    setStatus("connecting");
    setError(null);

    const eventSource = new EventSource(STREAM_ENDPOINT);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setStatus("open");
    };

    eventSource.onerror = () => {
      setStatus("error");
      setError("Connection lost. Retrying...");
      eventSource.close();
      eventSourceRef.current = null;
      // Reconnect after short delay
      setTimeout(() => {
        if (enabled) {
          setStatus("connecting");
        }
      }, 2000);
    };

    eventSource.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as ObservabilityEvent;
        setEvents((prev) => {
          const next = [parsed, ...prev];
          if (next.length > maxEvents) {
            next.length = maxEvents;
          }
          return next;
        });
      } catch (err) {
        console.error("Failed to parse observability event", err);
      }
    };

    return () => {
      eventSource.close();
      eventSourceRef.current = null;
      setStatus("closed");
    };
  }, [enabled, maxEvents]);

  const summary = useMemo(() => {
    const total = events.length;
    const byType = events.reduce<Record<string, number>>((acc, evt) => {
      const key = evt.event_type || evt.type || "unknown";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    return { total, byType };
  }, [events]);

  return {
    events,
    status,
    error,
    summary,
  };
}

