"use client";

import { useState } from "react";
import { MoreHorizontal, Eye, Pencil, Trash2 } from "lucide-react";
import { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PageHeader } from "@/components/composed/page-header";
import { DataTable } from "@/components/composed/data-table/data-table";
import type { Organization } from "@/types/tenant";

// Mock data
const mockOrganizations: (Organization & { users_count: number })[] = [
  {
    id: "1",
    name: "Acme Corporation",
    slug: "acme",
    created_at: "2024-01-15T00:00:00Z",
    updated_at: "2024-03-15T00:00:00Z",
    users_count: 25,
  },
  {
    id: "2",
    name: "TechStart Inc",
    slug: "techstart",
    created_at: "2024-02-01T00:00:00Z",
    updated_at: "2024-03-10T00:00:00Z",
    users_count: 12,
  },
  {
    id: "3",
    name: "Global Solutions",
    slug: "global-solutions",
    created_at: "2024-02-15T00:00:00Z",
    updated_at: "2024-03-05T00:00:00Z",
    users_count: 50,
  },
];

const columns: ColumnDef<(typeof mockOrganizations)[0]>[] = [
  {
    accessorKey: "name",
    header: "Organization",
    cell: ({ row }) => (
      <div>
        <div className="font-medium">{row.original.name}</div>
        <code className="text-xs text-muted-foreground">
          {row.original.slug}
        </code>
      </div>
    ),
  },
  {
    accessorKey: "users_count",
    header: "Users",
    cell: ({ row }) => (
      <Badge variant="secondary">{row.original.users_count} users</Badge>
    ),
  },
  {
    accessorKey: "created_at",
    header: "Created",
    cell: ({ row }) =>
      new Date(row.original.created_at).toLocaleDateString(),
  },
  {
    accessorKey: "updated_at",
    header: "Last Updated",
    cell: ({ row }) =>
      new Date(row.original.updated_at).toLocaleDateString(),
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
          <DropdownMenuItem asChild>
            <Link href={`/platform/organizations/${row.original.id}`}>
              <Eye className="mr-2 h-4 w-4" />
              View Details
            </Link>
          </DropdownMenuItem>
          <DropdownMenuItem>
            <Pencil className="mr-2 h-4 w-4" />
            Edit
          </DropdownMenuItem>
          <DropdownMenuItem className="text-destructive">
            <Trash2 className="mr-2 h-4 w-4" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    ),
  },
];

export default function PlatformOrganizationsPage() {
  const [organizations] = useState(mockOrganizations);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Organizations"
        description="Manage all organizations on the platform"
      />

      <DataTable
        columns={columns}
        data={organizations}
        emptyState={{
          title: "No organizations",
          description: "No organizations have been created yet.",
        }}
      />
    </div>
  );
}
