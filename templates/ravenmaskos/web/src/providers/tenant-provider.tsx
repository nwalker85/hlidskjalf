"use client";

import { createContext, useContext, useEffect } from "react";
import { useParams } from "next/navigation";
import { useTenantStore } from "@/stores/tenant-store";
import { useAuth } from "./auth-provider";
import { apiClient } from "@/lib/api/client";
import type {
  Organization,
  BusinessUnit,
  Team,
  Project,
} from "@/types/tenant";

interface TenantContextType {
  currentOrg: Organization | null;
  currentBusinessUnit: BusinessUnit | null;
  currentTeam: Team | null;
  currentProject: Project | null;
  setOrg: (org: Organization | null) => void;
  setBusinessUnit: (bu: BusinessUnit | null) => void;
  setTeam: (team: Team | null) => void;
  setProject: (project: Project | null) => void;
  isLoading: boolean;
}

const TenantContext = createContext<TenantContextType | undefined>(undefined);

export function TenantProvider({ children }: { children: React.ReactNode }) {
  const params = useParams();
  const { isAuthenticated } = useAuth();
  const {
    currentOrg,
    currentBusinessUnit,
    currentTeam,
    currentProject,
    setOrg,
    setBusinessUnit,
    setTeam,
    setProject,
    clearTenant,
  } = useTenantStore();

  const orgSlug = params?.orgSlug as string | undefined;

  // Fetch org by slug when route changes
  useEffect(() => {
    const loadOrg = async () => {
      if (!orgSlug || !isAuthenticated) {
        return;
      }

      // Skip if we already have the right org loaded
      if (currentOrg?.slug === orgSlug) {
        return;
      }

      try {
        const org = await apiClient.get<Organization>(
          `/organizations/by-slug/${orgSlug}`
        );
        setOrg(org);
      } catch {
        // Failed to load org - clear tenant context
        clearTenant();
      }
    };

    loadOrg();
  }, [orgSlug, isAuthenticated, currentOrg?.slug, setOrg, clearTenant]);

  // Clear tenant when user logs out
  useEffect(() => {
    if (!isAuthenticated) {
      clearTenant();
    }
  }, [isAuthenticated, clearTenant]);

  return (
    <TenantContext.Provider
      value={{
        currentOrg,
        currentBusinessUnit,
        currentTeam,
        currentProject,
        setOrg,
        setBusinessUnit,
        setTeam,
        setProject,
        isLoading: false,
      }}
    >
      {children}
    </TenantContext.Provider>
  );
}

export function useTenant() {
  const context = useContext(TenantContext);
  if (context === undefined) {
    throw new Error("useTenant must be used within a TenantProvider");
  }
  return context;
}
