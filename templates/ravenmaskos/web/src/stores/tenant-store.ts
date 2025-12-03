import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { Organization, BusinessUnit, Team, Project } from "@/types/tenant";

interface TenantState {
  currentOrg: Organization | null;
  currentBusinessUnit: BusinessUnit | null;
  currentTeam: Team | null;
  currentProject: Project | null;

  setOrg: (org: Organization | null) => void;
  setBusinessUnit: (bu: BusinessUnit | null) => void;
  setTeam: (team: Team | null) => void;
  setProject: (project: Project | null) => void;
  clearTenant: () => void;
  tenantHeaders: () => Record<string, string>;
}

export const useTenantStore = create<TenantState>()(
  persist(
    (set, get) => ({
      currentOrg: null,
      currentBusinessUnit: null,
      currentTeam: null,
      currentProject: null,

      setOrg: (org) =>
        set({
          currentOrg: org,
          // Clear child contexts when org changes
          currentBusinessUnit: null,
          currentTeam: null,
          currentProject: null,
        }),

      setBusinessUnit: (bu) =>
        set({
          currentBusinessUnit: bu,
          // Clear child contexts when BU changes
          currentTeam: null,
          currentProject: null,
        }),

      setTeam: (team) =>
        set({
          currentTeam: team,
          // Clear project when team changes
          currentProject: null,
        }),

      setProject: (project) =>
        set({
          currentProject: project,
        }),

      clearTenant: () =>
        set({
          currentOrg: null,
          currentBusinessUnit: null,
          currentTeam: null,
          currentProject: null,
        }),

      tenantHeaders: () => {
        const { currentOrg, currentBusinessUnit, currentTeam, currentProject } =
          get();
        const headers: Record<string, string> = {};

        if (currentOrg?.id) {
          headers["X-Org-ID"] = currentOrg.id;
        }
        if (currentBusinessUnit?.id) {
          headers["X-Business-Unit-ID"] = currentBusinessUnit.id;
        }
        if (currentTeam?.id) {
          headers["X-Team-ID"] = currentTeam.id;
        }
        if (currentProject?.id) {
          headers["X-Project-ID"] = currentProject.id;
        }

        return headers;
      },
    }),
    {
      name: "tenant-storage",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        currentOrg: state.currentOrg,
        currentBusinessUnit: state.currentBusinessUnit,
        currentTeam: state.currentTeam,
        currentProject: state.currentProject,
      }),
    }
  )
);
