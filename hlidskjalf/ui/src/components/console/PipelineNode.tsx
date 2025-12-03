"use client";

import React from "react";
import { cn } from "@/lib/utils";

export type NodeStatus = "idle" | "listening" | "processing" | "streaming" | "error" | "success";

interface PipelineNodeProps {
  name: string;
  status: NodeStatus;
  latency?: number;
  detail?: string;
  isExpanded?: boolean;
  onToggle?: () => void;
}

const statusStyles: Record<NodeStatus, string> = {
  idle: "bg-raven-800/50 border-raven-700",
  listening: "bg-huginn-600/20 border-huginn-500 animate-pulse",
  processing: "bg-odin-500/20 border-odin-400 shadow-lg shadow-odin-500/20",
  streaming: "bg-muninn-600/20 border-muninn-500",
  error: "bg-unhealthy/20 border-unhealthy",
  success: "bg-healthy/20 border-healthy",
};

const statusDotStyles: Record<NodeStatus, string> = {
  idle: "bg-raven-500",
  listening: "bg-huginn-400 animate-pulse",
  processing: "bg-odin-400 animate-ping",
  streaming: "bg-muninn-400",
  error: "bg-unhealthy animate-pulse",
  success: "bg-healthy",
};

export function PipelineNode({ 
  name, 
  status, 
  latency, 
  detail,
  isExpanded,
  onToggle 
}: PipelineNodeProps) {
  return (
    <div
      className={cn(
        "relative p-3 rounded-lg border backdrop-blur-sm transition-all duration-300 cursor-pointer",
        "hover:scale-[1.02] hover:shadow-md",
        statusStyles[status]
      )}
      onClick={onToggle}
    >
      <div className="flex items-center gap-3">
        {/* Status indicator */}
        <div className="relative">
          <div className={cn("w-2.5 h-2.5 rounded-full", statusDotStyles[status])} />
          {status === "processing" && (
            <div className="absolute inset-0 w-2.5 h-2.5 rounded-full bg-odin-400/50 animate-ping" />
          )}
        </div>
        
        {/* Node name */}
        <span className="font-mono text-sm text-raven-100">{name}</span>
        
        {/* Latency badge */}
        {latency !== undefined && (
          <span className="ml-auto font-mono text-xs text-raven-400">
            {latency}ms
          </span>
        )}
      </div>
      
      {/* Expanded detail */}
      {isExpanded && detail && (
        <div className="mt-2 pt-2 border-t border-raven-700/50">
          <p className="font-mono text-xs text-raven-400 truncate">{detail}</p>
        </div>
      )}
    </div>
  );
}

interface PipelineConnectorProps {
  isActive?: boolean;
}

export function PipelineConnector({ isActive }: PipelineConnectorProps) {
  return (
    <div className="flex justify-center py-1">
      <div className="relative w-0.5 h-6 bg-raven-700/50 overflow-hidden">
        {isActive && (
          <div className="absolute inset-0 w-full bg-gradient-to-b from-huginn-400 to-transparent animate-flow" />
        )}
      </div>
    </div>
  );
}

