"use client";

import React, { useState, useEffect } from "react";
import { cn } from "@/lib/utils";

export type ServiceStatus = "healthy" | "degraded" | "unhealthy" | "unknown";

export interface ServiceHealth {
  name: string;
  status: ServiceStatus;
  latency?: number;
  lastCheck?: Date;
  detail?: string;
}

const statusConfig: Record<ServiceStatus, { color: string; bg: string; label: string }> = {
  healthy: { color: "text-healthy", bg: "bg-healthy", label: "Healthy" },
  degraded: { color: "text-degraded", bg: "bg-degraded", label: "Degraded" },
  unhealthy: { color: "text-unhealthy", bg: "bg-unhealthy", label: "Unhealthy" },
  unknown: { color: "text-raven-500", bg: "bg-raven-500", label: "Unknown" },
};

interface ServiceStatusRowProps {
  service: ServiceHealth;
}

function ServiceStatusRow({ service }: ServiceStatusRowProps) {
  const config = statusConfig[service.status];
  
  return (
    <div className="flex items-center justify-between py-2 px-3 hover:bg-raven-800/30 rounded transition-colors">
      <div className="flex items-center gap-3">
        {/* Status LED */}
        <div className="relative">
          <div className={cn("w-2 h-2 rounded-full", config.bg)} />
          {service.status === "healthy" && (
            <div className={cn("absolute inset-0 w-2 h-2 rounded-full animate-ping", config.bg, "opacity-50")} />
          )}
        </div>
        
        {/* Service name */}
        <span className="font-mono text-sm text-raven-200">{service.name}</span>
      </div>
      
      <div className="flex items-center gap-3">
        {/* Latency */}
        {service.latency !== undefined && (
          <span className={cn(
            "font-mono text-xs",
            service.latency < 100 ? "text-healthy" : 
            service.latency < 500 ? "text-degraded" : "text-unhealthy"
          )}>
            {service.latency}ms
          </span>
        )}
        
        {/* Status label */}
        <span className={cn("text-xs font-medium uppercase tracking-wide", config.color)}>
          {config.label}
        </span>
      </div>
    </div>
  );
}

interface HealthPanelProps {
  services: ServiceHealth[];
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export function HealthPanel({ services, onRefresh, isRefreshing }: HealthPanelProps) {
  const healthyCount = services.filter(s => s.status === "healthy").length;
  const totalCount = services.length;
  const overallHealth = healthyCount === totalCount ? "healthy" : 
                        healthyCount > totalCount * 0.7 ? "degraded" : "unhealthy";

  return (
    <div className="bg-raven-900/50 rounded-lg border border-raven-700/50 backdrop-blur-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-raven-700/50">
        <div className="flex items-center gap-3">
          <h3 className="font-display font-semibold text-raven-100">System Health</h3>
          <span className={cn(
            "px-2 py-0.5 text-xs font-mono rounded-full",
            statusConfig[overallHealth].bg + "/20",
            statusConfig[overallHealth].color
          )}>
            {healthyCount}/{totalCount}
          </span>
        </div>
        
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className={cn(
              "p-1.5 rounded hover:bg-raven-700/50 transition-colors",
              isRefreshing && "animate-spin"
            )}
          >
            <svg className="w-4 h-4 text-raven-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        )}
      </div>
      
      {/* Service list */}
      <div className="divide-y divide-raven-800/50">
        {services.map(service => (
          <ServiceStatusRow key={service.name} service={service} />
        ))}
      </div>
    </div>
  );
}

// Hook for fetching service health
export function useServiceHealth() {
  const [services, setServices] = useState<ServiceHealth[]>([
    { name: "LangGraph", status: "unknown" },
    { name: "Ollama", status: "unknown" },
    { name: "Redis", status: "unknown" },
    { name: "PostgreSQL", status: "unknown" },
    { name: "Redpanda", status: "unknown" },
  ]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = async () => {
    setIsLoading(true);
    try {
      // Fetch from multiple endpoints in parallel
      const endpoints = [
        { name: "LangGraph", url: "/api/health/langgraph" },
        { name: "Ollama", url: "/api/health/ollama" },
        { name: "Redis", url: "/api/health/redis" },
        { name: "PostgreSQL", url: "/api/health/postgres" },
        { name: "Redpanda", url: "/api/health/redpanda" },
      ];

      const results = await Promise.allSettled(
        endpoints.map(async ({ name, url }) => {
          const start = Date.now();
          try {
            const res = await fetch(url, { cache: "no-store" });
            const data = await res.json().catch(() => ({}));
            const latency = data.latency ?? (Date.now() - start);
            return {
              name,
              status: data.status === "healthy" ? "healthy" as ServiceStatus : 
                      data.status === "degraded" ? "degraded" as ServiceStatus : 
                      "unhealthy" as ServiceStatus,
              latency,
              lastCheck: new Date(),
              detail: data.error || data.note,
            };
          } catch {
            return {
              name,
              status: "unhealthy" as ServiceStatus,
              latency: Date.now() - start,
              lastCheck: new Date(),
              detail: "Connection failed",
            };
          }
        })
      );

      setServices(
        results.map((r, i) => 
          r.status === "fulfilled" ? r.value : {
            name: endpoints[i].name,
            status: "unknown" as ServiceStatus,
            lastCheck: new Date(),
          }
        )
      );
      setError(null);
    } catch (err) {
      setError("Failed to fetch health status");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  return { services, isLoading, error, refresh: fetchHealth };
}

