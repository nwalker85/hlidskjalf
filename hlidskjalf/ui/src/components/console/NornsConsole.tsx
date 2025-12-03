"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { PipelineNode, PipelineConnector, NodeStatus } from "./PipelineNode";
import { EventTimeline, TimelineFilters, TimelineEvent, EventSubsystem, EventSeverity } from "./EventTimeline";
import { HealthPanel, useServiceHealth } from "./HealthPanel";
import { ControlSurface } from "./ControlSurface";
import { LLMConfigModal } from "@/components/llm-config";
import { cn } from "@/lib/utils";
import { useStreamContext } from "@/providers/Stream";
import { useQueryState } from "nuqs";
import { Settings, Cpu } from "lucide-react";

// Pipeline stage definitions
const PIPELINE_STAGES = [
  { id: "input", name: "User Input" },
  { id: "state", name: "Huginn State" },
  { id: "context", name: "Frigg Context" },
  { id: "agent", name: "Norns Agent" },
  { id: "tools", name: "Tool Execution" },
  { id: "memory", name: "Muninn Memory" },
  { id: "response", name: "Response" },
] as const;

interface PipelineStageState {
  status: NodeStatus;
  latency?: number;
  detail?: string;
}

interface NornsConsoleProps {
  children?: React.ReactNode;
}

export function NornsConsole({ children }: NornsConsoleProps) {
  // Get the actual stream context
  const stream = useStreamContext();
  const [threadId] = useQueryState("threadId");
  
  // LLM Configuration modal
  const [showLLMConfig, setShowLLMConfig] = useState(false);
  const [currentModel, setCurrentModel] = useState<string>("mistral-nemo:latest");
  
  // Pipeline state
  const [pipelineStates, setPipelineStates] = useState<Record<string, PipelineStageState>>(() =>
    Object.fromEntries(PIPELINE_STAGES.map(s => [s.id, { status: "idle" as NodeStatus }]))
  );
  const [expandedNode, setExpandedNode] = useState<string | null>(null);

  // Event timeline
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [activeSubsystems, setActiveSubsystems] = useState<EventSubsystem[]>(
    ["agent", "graph", "tool", "memory", "transport", "system"]
  );
  const [activeSeverities, setActiveSeverities] = useState<EventSeverity[]>(
    ["debug", "info", "success", "warning", "error"]
  );

  // Health monitoring
  const { services, isLoading: isHealthLoading, refresh: refreshHealth } = useServiceHealth();

  // Session metrics
  const [metrics, setMetrics] = useState({ latency: 0, tokensUsed: 0, turnCount: 0 });
  const [requestStart, setRequestStart] = useState<number | null>(null);

  // Derive connection status from stream
  const isConnected = threadId !== null || stream.messages.length > 0;
  const isStreaming = stream.isLoading;

  // Enhanced event logging helper
  const logEvent = useCallback((
    subsystem: EventSubsystem,
    severity: EventSeverity,
    message: string,
    options?: {
      detail?: string;
      data?: Record<string, unknown>;
      duration?: number;
      tags?: string[];
    }
  ) => {
    setEvents(prev => [...prev.slice(-500), {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
      timestamp: new Date(),
      subsystem,
      severity,
      message,
      detail: options?.detail,
      data: options?.data,
      duration: options?.duration,
      tags: options?.tags,
    }]);
  }, []);

  // Update pipeline state helper
  const updatePipeline = useCallback((stageId: string, state: Partial<PipelineStageState>) => {
    setPipelineStates(prev => ({
      ...prev,
      [stageId]: { ...prev[stageId], ...state },
    }));
  }, []);

  // Reset pipeline to idle
  const resetPipeline = useCallback(() => {
    PIPELINE_STAGES.forEach(s => updatePipeline(s.id, { status: "idle", latency: undefined, detail: undefined }));
  }, [updatePipeline]);

  // Watch for stream state changes
  useEffect(() => {
    if (isStreaming) {
      // Request started
      if (!requestStart) {
        setRequestStart(Date.now());
        updatePipeline("input", { status: "success", detail: "Message sent" });
        updatePipeline("state", { status: "processing" });
        updatePipeline("agent", { status: "listening" });
        logEvent("graph", "info", "Request started", { tags: ["stream"] });
      }
    } else if (requestStart) {
      // Request finished
      const latency = Date.now() - requestStart;
      setMetrics(prev => ({ 
        ...prev, 
        latency,
        turnCount: prev.turnCount + 1 
      }));
      
      updatePipeline("agent", { status: "success", latency });
      updatePipeline("response", { status: "success" });
      logEvent("graph", "success", "Response complete", { duration: latency, tags: ["stream"] });
      
      setRequestStart(null);
      
      // Reset pipeline after a delay
      setTimeout(resetPipeline, 2000);
    }
  }, [isStreaming, requestStart, updatePipeline, logEvent, resetPipeline]);

  // Watch for messages to detect tool calls - with rich logging
  const [lastLoggedMsgIndex, setLastLoggedMsgIndex] = useState(-1);
  
  useEffect(() => {
    // Log all new messages since last check
    const newMessages = stream.messages.slice(lastLoggedMsgIndex + 1);
    if (newMessages.length === 0) return;
    
    newMessages.forEach((msg) => {
      const msgType = msg.type;
      
      if (msgType === "human") {
        // Extract text content from message
        let content = "";
        if (typeof msg.content === "string") {
          content = msg.content;
        } else if (Array.isArray(msg.content)) {
          content = msg.content
            .map((c: any) => c.type === "text" ? c.text : JSON.stringify(c))
            .join(" ");
        } else {
          content = JSON.stringify(msg.content);
        }
        
        // Log user prompt - always show full content in detail
        logEvent("agent", "info", `📤 USER PROMPT`, {
          detail: content,
          tags: ["prompt", "user"],
        });
        setMetrics(prev => ({ ...prev, turnCount: prev.turnCount + 1 }));
        
      } else if (msgType === "ai") {
        const aiMsg = msg as any;
        
        // Log tool calls with full details
        if (aiMsg.tool_calls?.length > 0) {
          aiMsg.tool_calls.forEach((tc: { name: string; args?: unknown; id?: string }) => {
            updatePipeline("tools", { status: "processing", detail: tc.name });
            
            // Format args nicely
            const argsStr = tc.args ? JSON.stringify(tc.args, null, 2) : "{}";
            
            logEvent("tool", "info", `🔧 TOOL CALL: ${tc.name}`, {
              detail: `Arguments:\n${argsStr}`,
              data: tc.args as Record<string, unknown>,
              tags: ["tool-call", tc.name],
            });
          });
        }
        
        // Log AI response content - FULL response
        if (aiMsg.content) {
          let content = "";
          if (typeof aiMsg.content === "string") {
            content = aiMsg.content;
          } else if (Array.isArray(aiMsg.content)) {
            content = aiMsg.content
              .map((c: any) => c.type === "text" ? c.text : JSON.stringify(c))
              .join("\n");
          } else {
            content = JSON.stringify(aiMsg.content, null, 2);
          }
          
          updatePipeline("response", { status: "streaming" });
          
          // Log the full LLM response
          logEvent("agent", "success", `📥 LLM RESPONSE`, {
            detail: content,
            tags: ["response", "llm"],
          });
        }
        
      } else if (msgType === "tool") {
        const toolMsg = msg as any;
        const toolName = toolMsg.name || "unknown";
        
        // Get full tool result
        let content = "";
        if (typeof toolMsg.content === "string") {
          content = toolMsg.content;
        } else {
          content = JSON.stringify(toolMsg.content, null, 2);
        }
        
        // Check for errors in result
        const isError = content.toLowerCase().includes('"error"') || 
                        content.toLowerCase().includes('failed') ||
                        content.toLowerCase().includes('exception');
        
        updatePipeline("tools", { status: isError ? "error" : "success" });
        
        // Log full tool result
        logEvent("tool", isError ? "warning" : "success", `🔧 TOOL RESULT: ${toolName}`, {
          detail: content,
          tags: ["tool-result", toolName],
        });
      }
    });
    
    setLastLoggedMsgIndex(stream.messages.length - 1);
  }, [stream.messages, lastLoggedMsgIndex, updatePipeline, logEvent]);

  // Watch for errors
  useEffect(() => {
    if (stream.error) {
      const errorMsg = (stream.error as any)?.message || String(stream.error);
      logEvent("system", "error", "Stream error", { 
        detail: errorMsg,
        tags: ["error", "stream"],
      });
      updatePipeline("agent", { status: "error" });
    }
  }, [stream.error, logEvent, updatePipeline]);

  // Log thread changes
  useEffect(() => {
    if (threadId) {
      logEvent("system", "success", `Thread connected`, { 
        detail: threadId,
        tags: ["session"],
      });
    }
  }, [threadId, logEvent]);

  // Session handlers
  const handleNewSession = useCallback(() => {
    // Stop any in-progress stream
    if (stream.stop) {
      stream.stop();
    }
    setMetrics({ latency: 0, tokensUsed: 0, turnCount: 0 });
    setEvents([]);
    setLastLoggedMsgIndex(-1);
    resetPipeline();
    logEvent("system", "success", "New session started", { tags: ["session"] });
    // Clear thread ID via URL
    window.history.replaceState({}, '', window.location.pathname);
    window.location.reload();
  }, [stream, resetPipeline, logEvent]);

  const handleEndSession = useCallback(() => {
    if (stream.stop) {
      stream.stop();
    }
    logEvent("system", "info", "Session ended", { tags: ["session"] });
  }, [stream, logEvent]);

  const handleClearHistory = useCallback(() => {
    setEvents([]);
    setLastLoggedMsgIndex(-1);
    logEvent("system", "info", "Timeline cleared", { tags: ["ui"] });
  }, [logEvent]);

  const handleDumpState = useCallback(() => {
    const stateData = {
      threadId,
      messageCount: stream.messages.length,
      isLoading: stream.isLoading,
      pipeline: pipelineStates,
      eventCount: events.length,
      services: services.map(s => ({ name: s.name, status: s.status })),
      metrics,
    };
    console.log("=== Norns Console State Dump ===");
    console.log(JSON.stringify(stateData, null, 2));
    logEvent("system", "debug", "State dumped to console (F12)", { 
      data: stateData,
      tags: ["debug"],
    });
  }, [threadId, stream, pipelineStates, events, services, metrics, logEvent]);

  // Filter handlers
  const toggleSubsystem = (sub: EventSubsystem) => {
    setActiveSubsystems(prev =>
      prev.includes(sub) ? prev.filter(s => s !== sub) : [...prev, sub]
    );
  };

  const toggleSeverity = (sev: EventSeverity) => {
    setActiveSeverities(prev =>
      prev.includes(sev) ? prev.filter(s => s !== sev) : [...prev, sev]
    );
  };

  return (
    <div className="h-screen w-full flex flex-col bg-gradient-to-br from-[#0A0F1C] via-[#0D1420] to-[#111A2C] text-raven-100 overflow-hidden">
      {/* Header */}
      <header className="flex-none flex items-center justify-between px-6 py-3 border-b border-raven-800/50 bg-raven-950/80 backdrop-blur-sm relative z-50">
        <div className="flex items-center gap-4">
          <h1 className="font-display font-bold text-lg text-raven-50">
            Norns Intelligence Console
          </h1>
          <div className="flex items-center gap-2">
            <span className={cn(
              "w-2 h-2 rounded-full transition-colors",
              isConnected ? "bg-healthy animate-pulse" : "bg-unhealthy"
            )} />
            <span className="text-xs text-raven-400">
              {isStreaming ? "Streaming..." : isConnected ? "Connected" : "Disconnected"}
            </span>
          </div>
        </div>
        
        <div className="flex items-center gap-4 text-xs text-raven-400">
          {/* LLM Config Button */}
          <button
            onClick={() => setShowLLMConfig(true)}
            className="flex items-center gap-2 px-3 py-1.5 bg-raven-800/50 hover:bg-raven-700/50 border border-raven-700/50 rounded-lg transition-colors"
            title="Configure LLM Models"
          >
            <Cpu className="w-3.5 h-3.5 text-amber-400" />
            <span className="font-medium text-raven-200">{currentModel.split(":")[0]}</span>
            <Settings className="w-3 h-3 text-raven-500" />
          </button>
          
          {threadId && (
            <span className="font-mono">
              Thread: {threadId.slice(0, 16)}...
            </span>
          )}
          <span className="font-mono">v0.5.28</span>
        </div>
      </header>

      {/* Main Content - Fixed height grid */}
      <div className="flex-1 flex min-h-0 overflow-hidden">
        {/* Left Pane - Pipeline */}
        <aside className="w-56 flex-none flex flex-col border-r border-raven-800/50 bg-raven-950/50">
          <div className="flex-none p-3 border-b border-raven-800/50">
            <h2 className="text-xs font-semibold text-raven-400 uppercase tracking-wide">
              Agent Pipeline
            </h2>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-1">
            {PIPELINE_STAGES.map((stage, i) => (
              <React.Fragment key={stage.id}>
                <PipelineNode
                  name={stage.name}
                  status={pipelineStates[stage.id].status}
                  latency={pipelineStates[stage.id].latency}
                  detail={pipelineStates[stage.id].detail}
                  isExpanded={expandedNode === stage.id}
                  onToggle={() => setExpandedNode(
                    expandedNode === stage.id ? null : stage.id
                  )}
                />
                {i < PIPELINE_STAGES.length - 1 && (
                  <PipelineConnector 
                    isActive={
                      pipelineStates[stage.id].status === "streaming" ||
                      pipelineStates[stage.id].status === "processing"
                    }
                  />
                )}
              </React.Fragment>
            ))}
          </div>
        </aside>

        {/* Center - Chat + Timeline */}
        <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Chat Area - Takes remaining space */}
          <div className="flex-1 min-h-0 overflow-hidden">
            {children}
          </div>
          
          {/* Timeline Dock - Fixed height */}
          <div className="flex-none h-64 border-t border-raven-800/50 bg-raven-950/80 flex flex-col">
            <div className="flex-none flex items-center justify-between px-4 py-2 border-b border-raven-800/50">
              <h3 className="text-xs font-semibold text-raven-400 uppercase tracking-wide">Event Timeline</h3>
              <TimelineFilters
                activeSubsystems={activeSubsystems}
                activeSeverities={activeSeverities}
                onSubsystemToggle={toggleSubsystem}
                onSeverityToggle={toggleSeverity}
              />
            </div>
            <div className="flex-1 overflow-hidden px-2 pb-2">
              <EventTimeline
                events={events}
                maxHeight="100%"
                filter={{
                  subsystems: activeSubsystems,
                  severities: activeSeverities,
                }}
              />
            </div>
          </div>
        </main>

        {/* Right Pane - Controls + Health */}
        <aside className="w-64 flex-none flex flex-col border-l border-raven-800/50 bg-raven-950/50 overflow-y-auto">
          <div className="p-3 space-y-3">
            <ControlSurface
              sessionId={threadId}
              isConnected={isConnected}
              onNewSession={handleNewSession}
              onEndSession={handleEndSession}
              onClearHistory={handleClearHistory}
              onDumpState={handleDumpState}
              metrics={metrics}
            />
            
            <HealthPanel
              services={services}
              onRefresh={refreshHealth}
              isRefreshing={isHealthLoading}
            />
          </div>
        </aside>
      </div>

      {/* LLM Configuration Modal */}
      <LLMConfigModal
        isOpen={showLLMConfig}
        onClose={() => setShowLLMConfig(false)}
        sessionId={threadId || "default"}
        onConfigChange={(config) => {
          setCurrentModel(config.reasoning.model);
          logEvent("system", "success", "LLM configuration updated", {
            detail: `Reasoning: ${config.reasoning.provider}/${config.reasoning.model}`,
            tags: ["config", "llm"],
          });
        }}
      />
    </div>
  );
}

export default NornsConsole;
