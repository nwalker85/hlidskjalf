"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface ControlButtonProps {
  label: string;
  icon?: React.ReactNode;
  onClick: () => void;
  variant?: "primary" | "secondary" | "danger";
  disabled?: boolean;
  isActive?: boolean;
}

export function ControlButton({ 
  label, 
  icon, 
  onClick, 
  variant = "secondary",
  disabled,
  isActive
}: ControlButtonProps) {
  const variants = {
    primary: "bg-huginn-600 hover:bg-huginn-500 text-white",
    secondary: "bg-raven-800 hover:bg-raven-700 text-raven-200 border border-raven-600",
    danger: "bg-unhealthy/20 hover:bg-unhealthy/30 text-unhealthy border border-unhealthy/50",
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "flex items-center gap-2 px-3 py-2 rounded-lg font-mono text-sm transition-all",
        variants[variant],
        disabled && "opacity-50 cursor-not-allowed",
        isActive && "ring-2 ring-huginn-400/50"
      )}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

interface MetricChipProps {
  label: string;
  value: string | number;
  unit?: string;
  status?: "good" | "warning" | "critical";
}

export function MetricChip({ label, value, unit, status = "good" }: MetricChipProps) {
  const statusColors = {
    good: "text-healthy",
    warning: "text-degraded",
    critical: "text-unhealthy",
  };

  return (
    <div className="flex flex-col items-center p-2 bg-raven-800/50 rounded-lg border border-raven-700/50">
      <span className="text-xs text-raven-400 uppercase tracking-wide">{label}</span>
      <span className={cn("font-mono text-lg", statusColors[status])}>
        {value}{unit && <span className="text-xs ml-0.5">{unit}</span>}
      </span>
    </div>
  );
}

interface ControlSurfaceProps {
  sessionId: string | null;
  isConnected: boolean;
  onNewSession: () => void;
  onEndSession: () => void;
  onClearHistory: () => void;
  onDumpState: () => void;
  onShareLink?: () => void;
  metrics?: {
    latency?: number;
    tokensUsed?: number;
    turnCount?: number;
  };
}

export function ControlSurface({
  sessionId,
  isConnected,
  onNewSession,
  onEndSession,
  onClearHistory,
  onDumpState,
  onShareLink,
  metrics
}: ControlSurfaceProps) {
  return (
    <div className="flex flex-col gap-4 p-4 bg-raven-900/50 rounded-lg border border-raven-700/50 backdrop-blur-sm">
      {/* Session Info */}
      <div className="pb-3 border-b border-raven-700/50">
        <div className="flex items-center justify-between">
          <span className="text-xs text-raven-400 uppercase tracking-wide">Session</span>
          <div className={cn(
            "flex items-center gap-2 text-xs",
            isConnected ? "text-healthy" : "text-unhealthy"
          )}>
            <span className={cn(
              "w-1.5 h-1.5 rounded-full",
              isConnected ? "bg-healthy animate-pulse" : "bg-unhealthy"
            )} />
            {isConnected ? "Connected" : "Disconnected"}
          </div>
        </div>
        {sessionId && (
          <p className="mt-1 font-mono text-xs text-raven-400 truncate">
            {sessionId}
          </p>
        )}
      </div>

      {/* Session Controls */}
      <div className="space-y-2">
        <h4 className="text-xs text-raven-400 uppercase tracking-wide">Session Controls</h4>
        <div className="grid grid-cols-2 gap-2">
          <ControlButton
            label="New Session"
            onClick={onNewSession}
            variant="primary"
            icon={
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            }
          />
          <ControlButton
            label="End Session"
            onClick={onEndSession}
            variant="danger"
            disabled={!sessionId}
            icon={
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            }
          />
          <ControlButton
            label="Copy Session Link"
            onClick={() => onShareLink?.()}
            disabled={!onShareLink}
            icon={
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 12v7a1 1 0 001 1h7m8-8V5a1 1 0 00-1-1h-7m-2 10l9-9m0 0h-5m5 0v5"
                />
              </svg>
            }
          />
        </div>
      </div>

      {/* Debug Controls */}
      <div className="space-y-2">
        <h4 className="text-xs text-raven-400 uppercase tracking-wide">Debug</h4>
        <div className="grid grid-cols-2 gap-2">
          <ControlButton
            label="Clear History"
            onClick={onClearHistory}
            icon={
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            }
          />
          <ControlButton
            label="Dump State"
            onClick={onDumpState}
            icon={
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
            }
          />
        </div>
      </div>

      {/* Metrics */}
      {metrics && (
        <div className="space-y-2">
          <h4 className="text-xs text-raven-400 uppercase tracking-wide">Metrics</h4>
          <div className="grid grid-cols-3 gap-2">
            <MetricChip
              label="Latency"
              value={metrics.latency ?? "--"}
              unit="ms"
              status={
                !metrics.latency ? "good" :
                metrics.latency < 500 ? "good" :
                metrics.latency < 2000 ? "warning" : "critical"
              }
            />
            <MetricChip
              label="Tokens"
              value={metrics.tokensUsed ?? "--"}
              status="good"
            />
            <MetricChip
              label="Turns"
              value={metrics.turnCount ?? 0}
              status="good"
            />
          </div>
        </div>
      )}
    </div>
  );
}

