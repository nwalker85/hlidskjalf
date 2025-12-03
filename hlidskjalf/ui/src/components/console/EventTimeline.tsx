"use client";

import React, { useRef, useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { ChevronRight, ChevronDown, Copy, Check } from "lucide-react";

export type EventSeverity = "info" | "success" | "warning" | "error" | "debug";
export type EventSubsystem = "agent" | "graph" | "tool" | "memory" | "transport" | "system";

export interface TimelineEvent {
  id: string;
  timestamp: Date;
  subsystem: EventSubsystem;
  severity: EventSeverity;
  message: string;
  detail?: string;
  data?: Record<string, unknown>;
  duration?: number;
  parentId?: string;
  tags?: string[];
}

const severityStyles: Record<EventSeverity, { text: string; bg: string; border: string }> = {
  debug: { text: "text-zinc-400", bg: "bg-zinc-800/50", border: "border-zinc-700" },
  info: { text: "text-slate-300", bg: "bg-slate-800/50", border: "border-slate-700" },
  success: { text: "text-emerald-400", bg: "bg-emerald-900/30", border: "border-emerald-800" },
  warning: { text: "text-amber-400", bg: "bg-amber-900/30", border: "border-amber-800" },
  error: { text: "text-red-400", bg: "bg-red-900/30", border: "border-red-800" },
};

const subsystemLabels: Record<EventSubsystem, { label: string; color: string; fullName: string }> = {
  agent: { label: "AGT", color: "text-cyan-400 bg-cyan-900/50", fullName: "Agent" },
  graph: { label: "GRP", color: "text-purple-400 bg-purple-900/50", fullName: "Graph" },
  tool: { label: "TL", color: "text-orange-400 bg-orange-900/50", fullName: "Tool" },
  memory: { label: "MEM", color: "text-pink-400 bg-pink-900/50", fullName: "Memory" },
  transport: { label: "NET", color: "text-blue-400 bg-blue-900/50", fullName: "Transport" },
  system: { label: "SYS", color: "text-zinc-400 bg-zinc-800/50", fullName: "System" },
};

interface EventLogEntryProps {
  event: TimelineEvent;
  isLast?: boolean;
  isExpanded: boolean;
  onToggle: () => void;
}

function EventLogEntry({ event, isLast, isExpanded, onToggle }: EventLogEntryProps) {
  const [copied, setCopied] = useState(false);
  
  const time = event.timestamp.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const ms = event.timestamp.getMilliseconds().toString().padStart(3, "0");
  const sub = subsystemLabels[event.subsystem];
  const sev = severityStyles[event.severity];
  const hasExpandableContent = !!(event.detail || event.data);
  
  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    const content = JSON.stringify({
      timestamp: event.timestamp.toISOString(),
      subsystem: event.subsystem,
      severity: event.severity,
      message: event.message,
      detail: event.detail,
      data: event.data,
    }, null, 2);
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const handleClick = () => {
    if (hasExpandableContent) {
      onToggle();
    }
  };

  return (
    <div className={cn(
      "transition-colors",
      isLast && "bg-zinc-800/20",
      isExpanded && "bg-zinc-800/30"
    )}>
      {/* Main row - always clickable if has content */}
      <div 
        className={cn(
          "flex items-start gap-2 py-2 px-3 font-mono text-xs",
          hasExpandableContent && "cursor-pointer hover:bg-zinc-700/30",
          !hasExpandableContent && "cursor-default"
        )}
        onClick={handleClick}
        role={hasExpandableContent ? "button" : undefined}
        tabIndex={hasExpandableContent ? 0 : undefined}
        onKeyDown={(e) => {
          if (hasExpandableContent && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            onToggle();
          }
        }}
      >
        {/* Expand indicator */}
        <span className="w-4 flex-shrink-0 flex items-center justify-center pt-0.5">
          {hasExpandableContent ? (
            isExpanded ? (
              <ChevronDown className="w-3 h-3 text-zinc-400" />
            ) : (
              <ChevronRight className="w-3 h-3 text-zinc-500" />
            )
          ) : (
            <span className="w-1.5 h-1.5 rounded-full bg-zinc-600" />
          )}
        </span>
        
        {/* Timestamp */}
        <span className="text-zinc-500 whitespace-nowrap flex-shrink-0">
          {time}<span className="text-zinc-600">.{ms}</span>
        </span>
        
        {/* Subsystem badge */}
        <span className={cn(
          "px-1.5 py-0.5 rounded text-[10px] font-bold flex-shrink-0",
          sub.color
        )}>
          {sub.label}
        </span>
        
        {/* Duration if present */}
        {event.duration !== undefined && (
          <span className="px-1.5 py-0.5 rounded text-[10px] bg-zinc-700 text-zinc-300 flex-shrink-0">
            {event.duration}ms
          </span>
        )}
        
        {/* Message */}
        <span className={cn("flex-1 min-w-0", sev.text)}>
          {event.message}
        </span>
        
        {/* Tags */}
        {event.tags && event.tags.length > 0 && (
          <span className="flex gap-1 flex-shrink-0">
            {event.tags.slice(0, 2).map((tag, i) => (
              <span key={i} className="px-1.5 py-0.5 rounded text-[9px] bg-zinc-700/60 text-zinc-400">
                {tag}
              </span>
            ))}
          </span>
        )}
        
        {/* Copy button */}
        <button
          onClick={handleCopy}
          className="opacity-0 hover:opacity-100 focus:opacity-100 p-1 hover:bg-zinc-600 rounded transition-opacity flex-shrink-0"
          title="Copy event JSON"
        >
          {copied ? (
            <Check className="w-3 h-3 text-emerald-400" />
          ) : (
            <Copy className="w-3 h-3 text-zinc-500" />
          )}
        </button>
      </div>
      
      {/* Expanded content - shown when expanded */}
      {isExpanded && hasExpandableContent && (
        <div className={cn(
          "mx-6 mb-3 p-3 rounded border text-xs font-mono",
          sev.bg, sev.border
        )}>
          {event.detail && (
            <div className="text-zinc-200 whitespace-pre-wrap break-words leading-relaxed">
              {event.detail}
            </div>
          )}
          {event.data && (
            <pre className="mt-3 p-2 bg-zinc-900/70 rounded text-zinc-400 overflow-x-auto text-[11px] leading-relaxed">
              {JSON.stringify(event.data, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

interface EventTimelineProps {
  events: TimelineEvent[];
  maxHeight?: string;
  autoScroll?: boolean;
  filter?: {
    subsystems?: EventSubsystem[];
    severities?: EventSeverity[];
  };
}

export function EventTimeline({ 
  events, 
  maxHeight = "100%",
  autoScroll = true,
  filter
}: EventTimelineProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [shouldAutoScroll, setShouldAutoScroll] = useState(autoScroll);

  // Filter events
  const filteredEvents = events.filter(e => {
    if (filter?.subsystems && !filter.subsystems.includes(e.subsystem)) return false;
    if (filter?.severities && !filter.severities.includes(e.severity)) return false;
    return true;
  });

  // Auto-scroll
  useEffect(() => {
    if (shouldAutoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [filteredEvents.length, shouldAutoScroll]);

  const handleScroll = () => {
    if (scrollRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
      setShouldAutoScroll(isAtBottom);
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  return (
    <div 
      ref={scrollRef}
      onScroll={handleScroll}
      className="h-full overflow-y-auto bg-zinc-900/80 rounded border border-zinc-800"
      style={{ maxHeight }}
    >
      {filteredEvents.length === 0 ? (
        <div className="flex items-center justify-center h-full min-h-[80px] text-zinc-500 text-sm">
          Waiting for events...
        </div>
      ) : (
        <div className="divide-y divide-zinc-800/50">
          {filteredEvents.map((event, i) => (
            <EventLogEntry 
              key={event.id} 
              event={event} 
              isLast={i === filteredEvents.length - 1}
              isExpanded={expandedIds.has(event.id)}
              onToggle={() => toggleExpand(event.id)}
            />
          ))}
        </div>
      )}
      
      {/* Jump to bottom button */}
      {!shouldAutoScroll && filteredEvents.length > 5 && (
        <button
          onClick={() => {
            setShouldAutoScroll(true);
            if (scrollRef.current) {
              scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
            }
          }}
          className="sticky bottom-2 left-1/2 -translate-x-1/2 px-3 py-1.5 bg-zinc-700 hover:bg-zinc-600 rounded-full text-xs text-zinc-200 shadow-lg"
        >
          ↓ Latest
        </button>
      )}
    </div>
  );
}

interface TimelineFiltersProps {
  activeSubsystems: EventSubsystem[];
  activeSeverities: EventSeverity[];
  onSubsystemToggle: (subsystem: EventSubsystem) => void;
  onSeverityToggle: (severity: EventSeverity) => void;
}

export function TimelineFilters({
  activeSubsystems,
  activeSeverities,
  onSubsystemToggle,
  onSeverityToggle
}: TimelineFiltersProps) {
  const allSubsystems: EventSubsystem[] = ["agent", "graph", "tool", "memory", "transport", "system"];
  const allSeverities: EventSeverity[] = ["debug", "info", "success", "warning", "error"];

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Subsystem filters */}
      <div className="flex gap-0.5 bg-zinc-800/60 rounded p-0.5">
        {allSubsystems.map(sub => {
          const { label, color } = subsystemLabels[sub];
          const isActive = activeSubsystems.includes(sub);
          return (
            <button
              key={sub}
              onClick={() => onSubsystemToggle(sub)}
              className={cn(
                "px-2 py-0.5 text-[10px] font-bold rounded transition-all",
                isActive ? color : "text-zinc-600 hover:text-zinc-400"
              )}
              title={subsystemLabels[sub].fullName}
            >
              {label}
            </button>
          );
        })}
      </div>
      
      {/* Severity dots */}
      <div className="flex gap-1.5 items-center">
        {allSeverities.map(sev => {
          const isActive = activeSeverities.includes(sev);
          return (
            <button
              key={sev}
              onClick={() => onSeverityToggle(sev)}
              className={cn(
                "w-3 h-3 rounded-full transition-all border-2",
                sev === "debug" && (isActive ? "bg-zinc-400 border-zinc-400" : "border-zinc-600"),
                sev === "info" && (isActive ? "bg-slate-400 border-slate-400" : "border-slate-600"),
                sev === "success" && (isActive ? "bg-emerald-400 border-emerald-400" : "border-emerald-700"),
                sev === "warning" && (isActive ? "bg-amber-400 border-amber-400" : "border-amber-700"),
                sev === "error" && (isActive ? "bg-red-400 border-red-400" : "border-red-700"),
                !isActive && "opacity-40"
              )}
              title={sev}
            />
          );
        })}
      </div>
    </div>
  );
}
