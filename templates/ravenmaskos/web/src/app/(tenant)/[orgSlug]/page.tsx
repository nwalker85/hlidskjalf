"use client";

import { Users, Key, Shield, Activity } from "lucide-react";
import { PageHeader } from "@/components/composed/page-header";
import { StatCard } from "@/components/composed/stat-card";
import { useTenant } from "@/providers/tenant-provider";

export default function OrgDashboardPage() {
  const { currentOrg } = useTenant();

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Welcome to ${currentOrg?.name || "Dashboard"}`}
        description="Overview of your organization"
      />

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Total Users" value="--" icon={Users} />
        <StatCard title="Active Roles" value="--" icon={Shield} />
        <StatCard title="API Keys" value="--" icon={Key} />
        <StatCard title="Events Today" value="--" icon={Activity} />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border bg-card p-6">
          <h3 className="font-semibold mb-4">Recent Activity</h3>
          <p className="text-sm text-muted-foreground">
            No recent activity to display.
          </p>
        </div>
        <div className="rounded-lg border bg-card p-6">
          <h3 className="font-semibold mb-4">Quick Actions</h3>
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              Common tasks will appear here.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
