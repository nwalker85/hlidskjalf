"use client";

import { useState, useCallback } from "react";
import { apiClient, ApiError } from "@/lib/api/client";
import type {
  ApiKey,
  ApiKeyCreated,
  ApiKeyListResponse,
  CreateApiKeyRequest,
  UpdateApiKeyRequest,
  RevokeApiKeyResponse,
} from "@/types/tenant";

interface UseApiKeysState {
  apiKeys: ApiKey[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
  isLoading: boolean;
  error: string | null;
}

interface UseApiKeysReturn extends UseApiKeysState {
  fetchApiKeys: (options?: { page?: number; includeRevoked?: boolean }) => Promise<void>;
  getApiKey: (keyId: string) => Promise<ApiKey>;
  createApiKey: (data: CreateApiKeyRequest) => Promise<ApiKeyCreated>;
  updateApiKey: (keyId: string, data: UpdateApiKeyRequest) => Promise<ApiKey>;
  revokeApiKey: (keyId: string) => Promise<RevokeApiKeyResponse>;
  clearError: () => void;
}

export function useApiKeys(): UseApiKeysReturn {
  const [state, setState] = useState<UseApiKeysState>({
    apiKeys: [],
    total: 0,
    page: 1,
    pageSize: 20,
    hasMore: false,
    isLoading: false,
    error: null,
  });

  const fetchApiKeys = useCallback(
    async (options?: { page?: number; includeRevoked?: boolean }) => {
      setState((prev) => ({ ...prev, isLoading: true, error: null }));
      try {
        const params = new URLSearchParams();
        if (options?.page) params.set("page", options.page.toString());
        if (options?.includeRevoked) params.set("include_revoked", "true");

        const queryString = params.toString();
        const endpoint = `/api-keys${queryString ? `?${queryString}` : ""}`;
        const response = await apiClient.get<ApiKeyListResponse>(endpoint);

        setState({
          apiKeys: response.api_keys,
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
            : "Failed to fetch API keys";
        setState((prev) => ({ ...prev, isLoading: false, error: String(message) }));
      }
    },
    []
  );

  const getApiKey = useCallback(async (keyId: string): Promise<ApiKey> => {
    const response = await apiClient.get<ApiKey>(`/api-keys/${keyId}`);
    return response;
  }, []);

  const createApiKey = useCallback(
    async (data: CreateApiKeyRequest): Promise<ApiKeyCreated> => {
      const response = await apiClient.post<ApiKeyCreated>("/api-keys", data);
      // Refresh list
      await fetchApiKeys();
      return response;
    },
    [fetchApiKeys]
  );

  const updateApiKey = useCallback(
    async (keyId: string, data: UpdateApiKeyRequest): Promise<ApiKey> => {
      const response = await apiClient.patch<ApiKey>(`/api-keys/${keyId}`, data);
      // Update local state
      setState((prev) => ({
        ...prev,
        apiKeys: prev.apiKeys.map((k) => (k.id === keyId ? response : k)),
      }));
      return response;
    },
    []
  );

  const revokeApiKey = useCallback(
    async (keyId: string): Promise<RevokeApiKeyResponse> => {
      const response = await apiClient.post<RevokeApiKeyResponse>(
        `/api-keys/${keyId}/revoke`
      );
      // Remove from local state or mark as revoked
      setState((prev) => ({
        ...prev,
        apiKeys: prev.apiKeys.filter((k) => k.id !== keyId),
        total: prev.total - 1,
      }));
      return response;
    },
    []
  );

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  return {
    ...state,
    fetchApiKeys,
    getApiKey,
    createApiKey,
    updateApiKey,
    revokeApiKey,
    clearError,
  };
}
