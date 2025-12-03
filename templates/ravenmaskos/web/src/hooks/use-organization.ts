"use client";

import { useState, useCallback } from "react";
import { apiClient, ApiError } from "@/lib/api/client";

interface Organization {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  is_active: boolean;
  tier: "free" | "starter" | "professional" | "enterprise";
  domain: string | null;
  logo_url: string | null;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

interface OrganizationStats {
  org_id: string;
  user_count: number;
  api_key_count: number;
  tier: string;
  is_active: boolean;
}

interface UpdateOrganizationRequest {
  name?: string;
  description?: string;
  domain?: string;
  logo_url?: string;
  settings?: Record<string, unknown>;
}

interface UseOrganizationState {
  organization: Organization | null;
  stats: OrganizationStats | null;
  isLoading: boolean;
  error: string | null;
}

interface UseOrganizationReturn extends UseOrganizationState {
  fetchOrganization: () => Promise<void>;
  fetchStats: () => Promise<void>;
  updateOrganization: (data: UpdateOrganizationRequest) => Promise<Organization>;
  clearError: () => void;
}

export function useOrganization(): UseOrganizationReturn {
  const [state, setState] = useState<UseOrganizationState>({
    organization: null,
    stats: null,
    isLoading: false,
    error: null,
  });

  const fetchOrganization = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      const response = await apiClient.get<Organization>("/organizations/current");
      setState((prev) => ({
        ...prev,
        organization: response,
        isLoading: false,
      }));
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.data?.message || err.message
          : "Failed to fetch organization";
      setState((prev) => ({ ...prev, isLoading: false, error: String(message) }));
    }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const response = await apiClient.get<OrganizationStats>(
        "/organizations/current/stats"
      );
      setState((prev) => ({ ...prev, stats: response }));
    } catch (err) {
      console.error("Failed to fetch organization stats:", err);
    }
  }, []);

  const updateOrganization = useCallback(
    async (data: UpdateOrganizationRequest): Promise<Organization> => {
      const response = await apiClient.patch<Organization>(
        "/organizations/current",
        data
      );
      setState((prev) => ({ ...prev, organization: response }));
      return response;
    },
    []
  );

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  return {
    ...state,
    fetchOrganization,
    fetchStats,
    updateOrganization,
    clearError,
  };
}
