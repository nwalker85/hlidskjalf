"use client";

import { useState, useEffect } from "react";
import { RefreshCw, Search, Filter } from "lucide-react";
import { ColumnDef } from "@tanstack/react-table";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PageHeader } from "@/components/composed/page-header";
import { StatCard } from "@/components/composed/stat-card";
import { DataTable } from "@/components/composed/data-table/data-table";
import { useAuditLogs } from "@/hooks/use-audit-logs";
import type { AuditLogEntry } from "@/types/tenant";

export default function AuditLogPage() {
  const {
    logs,
    stats,
    total,
    isLoading,
    error,
    fetchLogs,
    fetchStats,
  } = useAuditLogs();

  const [actionFilter, setActionFilter] = useState<string>("");
  const [outcomeFilter, setOutcomeFilter] = useState<"success" | "failure" | "all">("all");

  useEffect(() => {
    fetchLogs();
    fetchStats();
  }, [fetchLogs, fetchStats]);

  const handleRefresh = () => {
    fetchLogs();
    fetchStats();
  };

  const handleFilter = () => {
    fetchLogs({
      filters: {
        action: actionFilter || undefined,
        outcome: outcomeFilter === "all" ? undefined : outcomeFilter,
      },
    });
  };

  const columns: ColumnDef<AuditLogEntry>[] = [
    {
      accessorKey: "timestamp",
      header: "Time",
      cell: ({ row }) => (
        <div className="text-sm whitespace-nowrap">
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
      accessorKey: "actor_type",
      header: "Actor",
      cell: ({ row }) => (
        <div>
          <Badge variant="outline">{row.original.actor_type}</Badge>
          <div className="text-xs text-muted-foreground mt-1">
            {row.original.actor_email || row.original.actor_id}
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
          <div className="text-xs text-muted-foreground truncate max-w-[150px]">
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
    {
      accessorKey: "ip_address",
      header: "IP Address",
      cell: ({ row }) => (
        <code className="text-xs text-muted-foreground">
          {row.original.ip_address || "-"}
        </code>
      ),
    },
  ];

  if (isLoading && logs.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Audit Log"
          description="View activity history for your organization"
        >
          <Button variant="outline" disabled>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </PageHeader>
        <div className="grid gap-4 md:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-[100px]" />
          ))}
        </div>
        <Skeleton className="h-[400px]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit Log"
        description="View activity history for your organization"
      >
        <Button variant="outline" onClick={handleRefresh}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </PageHeader>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {stats && (
        <div className="grid gap-4 md:grid-cols-4">
          <StatCard
            title="Total Events"
            value={stats.total_events}
            description="All time"
          />
          <StatCard
            title="Successful"
            value={stats.success_count}
            description={`${Math.round((stats.success_count / stats.total_events) * 100)}% success rate`}
          />
          <StatCard
            title="Failed"
            value={stats.failure_count}
            description="Actions that failed"
          />
          <StatCard
            title="Top Action"
            value={stats.top_actions[0]?.action.split(".")[1] || "-"}
            description={`${stats.top_actions[0]?.count || 0} times`}
          />
        </div>
      )}

      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Filter by action..."
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select
          value={outcomeFilter}
          onValueChange={(v) => setOutcomeFilter(v as "success" | "failure" | "all")}
        >
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Outcome" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All outcomes</SelectItem>
            <SelectItem value="success">Success</SelectItem>
            <SelectItem value="failure">Failure</SelectItem>
          </SelectContent>
        </Select>
        <Button variant="outline" onClick={handleFilter}>
          <Filter className="mr-2 h-4 w-4" />
          Apply
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={logs}
        emptyState={{
          title: "No audit events",
          description: "Activity will appear here as it happens.",
        }}
      />

      {total > 0 && (
        <div className="text-sm text-muted-foreground text-center">
          Showing {logs.length} of {total} events
        </div>
      )}
    </div>
  );
}
