"use client";

import { Building2, Users, Activity, Server } from "lucide-react";
import { PageHeader } from "@/components/composed/page-header";
import { StatCard } from "@/components/composed/stat-card";

export default function PlatformDashboardPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Dashboard"
        description="System-wide overview and management"
      />

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Organizations"
          value="--"
          icon={Building2}
          description="Across all tenants"
        />
        <StatCard
          title="Total Users"
          value="--"
          icon={Users}
          description="Platform-wide"
        />
        <StatCard
          title="API Requests (24h)"
          value="--"
          icon={Activity}
          description="Last 24 hours"
        />
        <StatCard
          title="System Health"
          value="Healthy"
          icon={Server}
          description="All services operational"
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border bg-card p-6">
          <h3 className="font-semibold mb-4">Recent Organizations</h3>
          <p className="text-sm text-muted-foreground">
            No organizations to display.
          </p>
        </div>
        <div className="rounded-lg border bg-card p-6">
          <h3 className="font-semibold mb-4">System Alerts</h3>
          <p className="text-sm text-muted-foreground">
            No active alerts.
          </p>
        </div>
      </div>
    </div>
  );
}
