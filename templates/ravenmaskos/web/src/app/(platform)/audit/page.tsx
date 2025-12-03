"use client";

import { useState } from "react";
import { RefreshCw, Download } from "lucide-react";
import { ColumnDef } from "@tanstack/react-table";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/composed/page-header";
import { DataTable } from "@/components/composed/data-table/data-table";
import type { AuditLogEntry } from "@/types/tenant";

// Mock data - platform-wide audit
const mockPlatformAudit: (AuditLogEntry & { org_name: string })[] = [
  {
    id: "1",
    timestamp: "2024-03-15T14:30:00Z",
    actor_id: "platform_admin",
    actor_type: "user",
    action: "org.create",
    resource_type: "organization",
    resource_id: "org3",
    org_id: "platform",
    org_name: "Platform",
    ip_address: "192.168.1.1",
    user_agent: "Mozilla/5.0",
    outcome: "success",
    details: { org_name: "New Corp" },
  },
  {
    id: "2",
    timestamp: "2024-03-15T14:25:00Z",
    actor_id: "platform_admin",
    actor_type: "user",
    action: "user.suspend",
    resource_type: "user",
    resource_id: "user5",
    org_id: "org1",
    org_name: "Acme Corporation",
    ip_address: "192.168.1.1",
    user_agent: "Mozilla/5.0",
    outcome: "success",
    details: { reason: "Policy violation" },
  },
  {
    id: "3",
    timestamp: "2024-03-15T14:20:00Z",
    actor_id: "system",
    actor_type: "service",
    action: "config.update",
    resource_type: "system",
    resource_id: "rate_limit",
    org_id: "platform",
    org_name: "Platform",
    ip_address: "10.0.0.1",
    user_agent: "SystemService/1.0",
    outcome: "success",
    details: { setting: "rate_limit", value: 100 },
  },
];

const columns: ColumnDef<(typeof mockPlatformAudit)[0]>[] = [
  {
    accessorKey: "timestamp",
    header: "Time",
    cell: ({ row }) => (
      <div className="text-sm">
        {new Date(row.original.timestamp).toLocaleString()}
      </div>
    ),
  },
  {
    accessorKey: "action",
    header: "Action",
    cell: ({ row }) => (
      <code className="text-sm bg-muted px-2 py-1 rounded">
        {row.original.action}
      </code>
    ),
  },
  {
    accessorKey: "org_name",
    header: "Scope",
    cell: ({ row }) => (
      <Badge variant="outline">{row.original.org_name}</Badge>
    ),
  },
  {
    accessorKey: "actor_type",
    header: "Actor",
    cell: ({ row }) => (
      <div>
        <Badge
          variant={
            row.original.actor_type === "user" ? "secondary" : "outline"
          }
        >
          {row.original.actor_type}
        </Badge>
        <div className="text-xs text-muted-foreground mt-1">
          {row.original.actor_id}
        </div>
      </div>
    ),
  },
  {
    accessorKey: "resource_type",
    header: "Resource",
    cell: ({ row }) => (
      <div className="text-sm">
        <span className="font-medium">{row.original.resource_type}</span>
        <div className="text-xs text-muted-foreground">
          {row.original.resource_id}
        </div>
      </div>
    ),
  },
  {
    accessorKey: "outcome",
    header: "Status",
    cell: ({ row }) => (
      <Badge
        variant={row.original.outcome === "success" ? "default" : "destructive"}
      >
        {row.original.outcome}
      </Badge>
    ),
  },
];

export default function PlatformAuditPage() {
  const [auditLog] = useState(mockPlatformAudit);
  const [search, setSearch] = useState("");

  const filteredLog = auditLog.filter(
    (entry) =>
      entry.action.toLowerCase().includes(search.toLowerCase()) ||
      entry.actor_id.toLowerCase().includes(search.toLowerCase()) ||
      entry.org_name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Audit Log"
        description="View all activity across the platform"
      >
        <div className="flex gap-2">
          <Button variant="outline">
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
          <Button variant="outline">
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </div>
      </PageHeader>

      <div className="flex items-center gap-4">
        <Input
          placeholder="Search audit log..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />
      </div>

      <DataTable
        columns={columns}
        data={filteredLog}
        emptyState={{
          title: "No audit events",
          description: search
            ? "Try adjusting your search."
            : "No audit events recorded yet.",
        }}
      />
    </div>
  );
}
