"use client";

import { useState, useEffect } from "react";
import { Plus, MoreHorizontal, Copy, Trash2, Key } from "lucide-react";
import { ColumnDef } from "@tanstack/react-table";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PageHeader } from "@/components/composed/page-header";
import { DataTable } from "@/components/composed/data-table/data-table";
import {
  CreateApiKeyDialog,
  RevokeApiKeyDialog,
} from "@/components/features/api-keys";
import { useApiKeys } from "@/hooks/use-api-keys";
import { useToast } from "@/hooks/use-toast";
import type { ApiKey } from "@/types/tenant";

export default function ApiKeysPage() {
  const { toast } = useToast();
  const {
    apiKeys,
    isLoading,
    error,
    fetchApiKeys,
    createApiKey,
    revokeApiKey,
  } = useApiKeys();

  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [revokeDialogOpen, setRevokeDialogOpen] = useState(false);
  const [selectedKey, setSelectedKey] = useState<ApiKey | null>(null);

  useEffect(() => {
    fetchApiKeys();
  }, [fetchApiKeys]);

  const handleRevoke = (apiKey: ApiKey) => {
    setSelectedKey(apiKey);
    setRevokeDialogOpen(true);
  };

  const columns: ColumnDef<ApiKey>[] = [
    {
      accessorKey: "name",
      header: "Name",
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <Key className="h-4 w-4 text-muted-foreground" />
          <div>
            <div className="font-medium">{row.original.name}</div>
            <code className="text-xs text-muted-foreground">
              {row.original.key_prefix}...
            </code>
          </div>
        </div>
      ),
    },
    {
      accessorKey: "description",
      header: "Description",
      cell: ({ row }) => (
        <span className="text-muted-foreground">
          {row.original.description || "-"}
        </span>
      ),
    },
    {
      accessorKey: "scopes",
      header: "Scopes",
      cell: ({ row }) => (
        <div className="flex gap-1 flex-wrap">
          {row.original.scopes.length > 0 ? (
            row.original.scopes.slice(0, 2).map((scope) => (
              <Badge key={scope} variant="outline" className="text-xs">
                {scope}
              </Badge>
            ))
          ) : (
            <span className="text-muted-foreground text-sm">All access</span>
          )}
          {row.original.scopes.length > 2 && (
            <Badge variant="outline" className="text-xs">
              +{row.original.scopes.length - 2}
            </Badge>
          )}
        </div>
      ),
    },
    {
      accessorKey: "usage_count",
      header: "Usage",
      cell: ({ row }) => (
        <span className="text-muted-foreground">
          {row.original.usage_count.toLocaleString()} requests
        </span>
      ),
    },
    {
      accessorKey: "last_used_at",
      header: "Last Used",
      cell: ({ row }) =>
        row.original.last_used_at ? (
          new Date(row.original.last_used_at).toLocaleDateString()
        ) : (
          <span className="text-muted-foreground">Never</span>
        ),
    },
    {
      accessorKey: "expires_at",
      header: "Expires",
      cell: ({ row }) => {
        if (!row.original.expires_at) {
          return <span className="text-muted-foreground">Never</span>;
        }
        const expiry = new Date(row.original.expires_at);
        const isExpired = expiry < new Date();
        return (
          <span className={isExpired ? "text-destructive" : ""}>
            {expiry.toLocaleDateString()}
            {isExpired && " (expired)"}
          </span>
        );
      },
    },
    {
      accessorKey: "is_active",
      header: "Status",
      cell: ({ row }) => (
        <Badge variant={row.original.is_active ? "default" : "destructive"}>
          {row.original.is_active ? "Active" : "Revoked"}
        </Badge>
      ),
    },
    {
      id: "actions",
      cell: ({ row }) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem
              onClick={() => {
                navigator.clipboard.writeText(row.original.key_prefix);
                toast({
                  title: "Copied",
                  description: "API key prefix copied to clipboard",
                });
              }}
            >
              <Copy className="mr-2 h-4 w-4" />
              Copy Prefix
            </DropdownMenuItem>
            {row.original.is_active && (
              <DropdownMenuItem
                className="text-destructive"
                onClick={() => handleRevoke(row.original)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Revoke
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ];

  if (isLoading && apiKeys.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader title="API Keys" description="Manage API access keys">
          <Button disabled>
            <Plus className="mr-2 h-4 w-4" />
            Create API Key
          </Button>
        </PageHeader>
        <div className="space-y-4">
          <Skeleton className="h-[400px] w-full" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="API Keys" description="Manage API access keys">
        <Button onClick={() => setCreateDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create API Key
        </Button>
      </PageHeader>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      <DataTable
        columns={columns}
        data={apiKeys}
        emptyState={{
          title: "No API keys",
          description: "Create an API key to access the API programmatically.",
        }}
      />

      <CreateApiKeyDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onCreate={createApiKey}
      />

      <RevokeApiKeyDialog
        apiKey={selectedKey}
        open={revokeDialogOpen}
        onOpenChange={setRevokeDialogOpen}
        onRevoke={revokeApiKey}
      />
    </div>
  );
}
