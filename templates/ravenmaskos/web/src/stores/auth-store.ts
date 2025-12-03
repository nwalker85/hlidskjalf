import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { CurrentUser } from "@/types/auth";

interface AuthState {
  user: CurrentUser | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  setUser: (user: CurrentUser | null) => void;
  setAccessToken: (token: string | null) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
  hasRole: (role: string) => boolean;
  hasScope: (scope: string) => boolean;
  hasAnyRole: (roles: string[]) => boolean;
  hasAllScopes: (scopes: string[]) => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      isLoading: true,

      setUser: (user) =>
        set({
          user,
          isAuthenticated: !!user,
        }),

      setAccessToken: (accessToken) =>
        set({
          accessToken,
        }),

      setLoading: (isLoading) => set({ isLoading }),

      logout: () =>
        set({
          user: null,
          accessToken: null,
          isAuthenticated: false,
        }),

      hasRole: (role) => {
        const { user } = get();
        return user?.roles.includes(role) ?? false;
      },

      hasScope: (scope) => {
        const { user } = get();
        return user?.scopes.includes(scope) ?? false;
      },

      hasAnyRole: (roles) => {
        const { user } = get();
        return roles.some((role) => user?.roles.includes(role)) ?? false;
      },

      hasAllScopes: (scopes) => {
        const { user } = get();
        return scopes.every((scope) => user?.scopes.includes(scope)) ?? false;
      },
    }),
    {
      name: "auth-storage",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        // Only persist accessToken - user will be refetched on page load
        accessToken: state.accessToken,
      }),
    }
  )
);
