"use client";

import { createContext, useContext, useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { apiClient } from "@/lib/api/client";
import type { CurrentUser } from "@/types/auth";

interface AuthContextType {
  user: CurrentUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  hasRole: (role: string) => boolean;
  hasScope: (scope: string) => boolean;
  hasAnyRole: (roles: string[]) => boolean;
  hasAllScopes: (scopes: string[]) => boolean;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const {
    user,
    isAuthenticated,
    isLoading,
    accessToken,
    setUser,
    setLoading,
    hasRole,
    hasScope,
    hasAnyRole,
    hasAllScopes,
    logout: storeLogout,
  } = useAuthStore();

  // Fetch user on initial load if we have an access token
  useEffect(() => {
    const initAuth = async () => {
      if (!accessToken) {
        setLoading(false);
        return;
      }

      try {
        const userData = await apiClient.get<CurrentUser>("/auth/me");
        setUser(userData);
      } catch {
        // Token invalid or expired, try refresh
        try {
          const response = await fetch("/api/auth/refresh", {
            method: "POST",
            credentials: "include",
          });

          if (response.ok) {
            const data = await response.json();
            useAuthStore.getState().setAccessToken(data.access_token);

            // Retry fetching user
            const userData = await apiClient.get<CurrentUser>("/auth/me");
            setUser(userData);
          } else {
            storeLogout();
          }
        } catch {
          storeLogout();
        }
      } finally {
        setLoading(false);
      }
    };

    initAuth();
  }, [accessToken, setUser, setLoading, storeLogout]);

  const logout = async () => {
    try {
      // Call BFF logout to clear HttpOnly cookie
      await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "include",
      });
    } finally {
      storeLogout();
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        isLoading,
        hasRole,
        hasScope,
        hasAnyRole,
        hasAllScopes,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
