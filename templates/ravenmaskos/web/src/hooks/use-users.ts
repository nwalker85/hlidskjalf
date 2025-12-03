"use client";

import { useState, useCallback } from "react";
import { apiClient, ApiError } from "@/lib/api/client";
import type {
  User,
  UserListResponse,
  CreateUserRequest,
  UpdateUserRequest,
  UpdateUserRolesRequest,
  InviteUserRequest,
  InviteUserResponse,
  BulkUserActionRequest,
  BulkUserActionResponse,
} from "@/types/tenant";

interface UseUsersState {
  users: User[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
  isLoading: boolean;
  error: string | null;
}

interface UseUsersReturn extends UseUsersState {
  fetchUsers: (options?: { page?: number; search?: string; isActive?: boolean }) => Promise<void>;
  getUser: (userId: string) => Promise<User>;
  createUser: (data: CreateUserRequest) => Promise<User>;
  updateUser: (userId: string, data: UpdateUserRequest) => Promise<User>;
  updateUserRoles: (userId: string, data: UpdateUserRolesRequest) => Promise<User>;
  deleteUser: (userId: string) => Promise<void>;
  inviteUser: (data: InviteUserRequest) => Promise<InviteUserResponse>;
  bulkAction: (data: BulkUserActionRequest) => Promise<BulkUserActionResponse>;
  clearError: () => void;
}

export function useUsers(): UseUsersReturn {
  const [state, setState] = useState<UseUsersState>({
    users: [],
    total: 0,
    page: 1,
    pageSize: 20,
    hasMore: false,
    isLoading: false,
    error: null,
  });

  const fetchUsers = useCallback(
    async (options?: { page?: number; search?: string; isActive?: boolean }) => {
      setState((prev) => ({ ...prev, isLoading: true, error: null }));
      try {
        const params = new URLSearchParams();
        if (options?.page) params.set("page", options.page.toString());
        if (options?.search) params.set("search", options.search);
        if (options?.isActive !== undefined) {
          params.set("is_active", options.isActive.toString());
        }

        const queryString = params.toString();
        const endpoint = `/users${queryString ? `?${queryString}` : ""}`;
        const response = await apiClient.get<UserListResponse>(endpoint);

        setState({
          users: response.users,
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
            : "Failed to fetch users";
        setState((prev) => ({ ...prev, isLoading: false, error: String(message) }));
      }
    },
    []
  );

  const getUser = useCallback(async (userId: string): Promise<User> => {
    const response = await apiClient.get<User>(`/users/${userId}`);
    return response;
  }, []);

  const createUser = useCallback(
    async (data: CreateUserRequest): Promise<User> => {
      const response = await apiClient.post<User>("/users", data);
      // Refresh list
      await fetchUsers();
      return response;
    },
    [fetchUsers]
  );

  const updateUser = useCallback(
    async (userId: string, data: UpdateUserRequest): Promise<User> => {
      const response = await apiClient.patch<User>(`/users/${userId}`, data);
      // Update local state
      setState((prev) => ({
        ...prev,
        users: prev.users.map((u) => (u.id === userId ? response : u)),
      }));
      return response;
    },
    []
  );

  const updateUserRoles = useCallback(
    async (userId: string, data: UpdateUserRolesRequest): Promise<User> => {
      const response = await apiClient.put<User>(`/users/${userId}/roles`, data);
      // Update local state
      setState((prev) => ({
        ...prev,
        users: prev.users.map((u) => (u.id === userId ? response : u)),
      }));
      return response;
    },
    []
  );

  const deleteUser = useCallback(
    async (userId: string): Promise<void> => {
      await apiClient.delete(`/users/${userId}`);
      // Remove from local state
      setState((prev) => ({
        ...prev,
        users: prev.users.filter((u) => u.id !== userId),
        total: prev.total - 1,
      }));
    },
    []
  );

  const inviteUser = useCallback(
    async (data: InviteUserRequest): Promise<InviteUserResponse> => {
      const response = await apiClient.post<InviteUserResponse>("/users/invite", data);
      // Refresh list
      await fetchUsers();
      return response;
    },
    [fetchUsers]
  );

  const bulkAction = useCallback(
    async (data: BulkUserActionRequest): Promise<BulkUserActionResponse> => {
      const response = await apiClient.post<BulkUserActionResponse>("/users/bulk", data);
      // Refresh list
      await fetchUsers();
      return response;
    },
    [fetchUsers]
  );

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  return {
    ...state,
    fetchUsers,
    getUser,
    createUser,
    updateUser,
    updateUserRoles,
    deleteUser,
    inviteUser,
    bulkAction,
    clearError,
  };
}
