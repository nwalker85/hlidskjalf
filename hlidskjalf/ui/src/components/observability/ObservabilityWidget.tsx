"use client";

import { Activity, AlertTriangle, Radio, RefreshCcw } from "lucide-react";
import { useMemo } from "react";
import { useObservabilityStream } from "@/hooks/useObservabilityStream";
import clsx from "clsx";

const STATUS_LABELS = {
  connecting: "Connecting",
  open: "Live",
  error: "Error",
  closed: "Stopped",
} as const;

const STATUS_COLORS = {
  connecting: "text-amber-400 bg-amber-400/10",
  open: "text-emerald-400 bg-emerald-400/10",
  error: "text-rose-400 bg-rose-400/10",
  closed: "text-raven-400 bg-raven-400/10",
} as const;

export function ObservabilityWidget() {
  const { events, status, error, summary } = useObservabilityStream({
    enabled: true,
    maxEvents: 100,
  });

  const topTypes = useMemo(() => {
    const entries = Object.entries(summary.byType || {});
    return entries
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4)
      .map(([type, count]) => ({ type, count }));
  }, [summary]);

  return (
    <section className="card p-4 space-y-4">
      <header className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold tracking-widest text-raven-500 uppercase">
            Observability Stream
          </p>
          <h3 className="text-lg font-display text-raven-100 flex items-center gap-2">
            <Radio className="w-4 h-4 text-emerald-400" />
            Norns Squad Telemetry
          </h3>
          <p className="text-sm text-raven-400">
            Live events from Redpanda & observability agents.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={clsx(
              "inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium",
              STATUS_COLORS[status],
            )}
          >
            <span className="w-2 h-2 rounded-full bg-current animate-ping" />
            {STATUS_LABELS[status]}
          </span>
          <button
            className="p-2 rounded-lg border border-raven-800 text-raven-400 hover:text-raven-200 hover:border-raven-700 transition-colors"
            onClick={() => location.reload()}
            title="Reload page"
          >
            <RefreshCcw className="w-4 h-4" />
          </button>
        </div>
      </header>

      {error && (
        <div className="flex items-center gap-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
          <AlertTriangle className="w-4 h-4" />
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <div className="rounded-lg border border-raven-800/50 bg-raven-900/30 px-3 py-2">
          <p className="text-xs text-raven-500">Events (5m)</p>
          <p className="text-xl font-semibold text-raven-100">{summary.total}</p>
        </div>
        {topTypes.map(({ type, count }) => (
          <div
            key={type}
            className="rounded-lg border border-raven-800/50 bg-raven-900/30 px-3 py-2"
          >
            <p className="text-xs text-raven-500 truncate">{type}</p>
            <p className="text-lg font-semibold text-raven-100">{count}</p>
          </div>
        ))}
      </div>

      <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
        {events.length === 0 && (
          <div className="text-sm text-raven-500 flex items-center gap-2">
            <Activity className="w-4 h-4 animate-pulse" />
            Waiting for events...
          </div>
        )}
        {events.map((event, index) => (
          <article
            key={`${event.timestamp}-${index}`}
            className="rounded-lg border border-raven-800/60 bg-raven-900/40 p-3"
          >
            <div className="flex flex-wrap items-center gap-2 text-xs text-raven-400">
              <span className="rounded-full bg-raven-800/80 px-2 py-0.5 text-emerald-300">
                {event.event_type || event.type}
              </span>
              {event.source && (
                <span className="text-raven-500">from {event.source}</span>
              )}
              {event.target && (
                <span className="text-raven-500">→ {event.target}</span>
              )}
              {event.timestamp && (
                <span className="ml-auto">
                  {new Date(event.timestamp).toLocaleTimeString()}
                </span>
              )}
            </div>
            {event.message && (
              <p className="mt-2 text-sm text-raven-200">{event.message}</p>
            )}
            {event.payload && Object.keys(event.payload).length > 0 && (
              <pre className="mt-2 text-[11px] text-raven-400 bg-raven-950/60 rounded-md p-2 overflow-x-auto">
                {JSON.stringify(event.payload, null, 2)}
              </pre>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

