"use client";

import { useState, useCallback } from "react";
import { apiClient, ApiError } from "@/lib/api/client";
import type { AuditLogEntry } from "@/types/tenant";

interface AuditLogListResponse {
  logs: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

interface AuditLogStats {
  total_events: number;
  success_count: number;
  failure_count: number;
  top_actions: { action: string; count: number }[];
  top_actors: { actor_id: string; count: number }[];
}

interface AuditLogFilters {
  actor_id?: string;
  actor_type?: "user" | "service" | "system";
  action?: string;
  resource_type?: string;
  outcome?: "success" | "failure";
  start_date?: string;
  end_date?: string;
}

interface UseAuditLogsState {
  logs: AuditLogEntry[];
  stats: AuditLogStats | null;
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
  isLoading: boolean;
  error: string | null;
}

interface UseAuditLogsReturn extends UseAuditLogsState {
  fetchLogs: (options?: { page?: number; filters?: AuditLogFilters }) => Promise<void>;
  fetchStats: () => Promise<void>;
  clearError: () => void;
}

export function useAuditLogs(): UseAuditLogsReturn {
  const [state, setState] = useState<UseAuditLogsState>({
    logs: [],
    stats: null,
    total: 0,
    page: 1,
    pageSize: 50,
    hasMore: false,
    isLoading: false,
    error: null,
  });

  const fetchLogs = useCallback(
    async (options?: { page?: number; filters?: AuditLogFilters }) => {
      setState((prev) => ({ ...prev, isLoading: true, error: null }));
      try {
        const params = new URLSearchParams();
        if (options?.page) params.set("page", options.page.toString());
        if (options?.filters) {
          const { filters } = options;
          if (filters.actor_id) params.set("actor_id", filters.actor_id);
          if (filters.actor_type) params.set("actor_type", filters.actor_type);
          if (filters.action) params.set("action", filters.action);
          if (filters.resource_type) params.set("resource_type", filters.resource_type);
          if (filters.outcome) params.set("outcome", filters.outcome);
          if (filters.start_date) params.set("start_date", filters.start_date);
          if (filters.end_date) params.set("end_date", filters.end_date);
        }

        const queryString = params.toString();
        const endpoint = `/audit-logs${queryString ? `?${queryString}` : ""}`;
        const response = await apiClient.get<AuditLogListResponse>(endpoint);

        setState({
          logs: response.logs,
          stats: state.stats,
          total: response.total,
          page: response.page,
          pageSize: response.page_size,
          hasMore: response.has_more,
          isLoading: false,
          error: null,
        });
      } catch (err) {
        const message =
          err instanceof ApiError
            ? err.data?.message || err.message
            : "Failed to fetch audit logs";
        setState((prev) => ({ ...prev, isLoading: false, error: String(message) }));
      }
    },
    [state.stats]
  );

  const fetchStats = useCallback(async () => {
    try {
      const response = await apiClient.get<AuditLogStats>("/audit-logs/stats");
      setState((prev) => ({ ...prev, stats: response }));
    } catch (err) {
      console.error("Failed to fetch audit log stats:", err);
    }
  }, []);

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  return {
    ...state,
    fetchLogs,
    fetchStats,
    clearError,
  };
}
