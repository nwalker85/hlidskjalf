"use client";

import { useState } from "react";
import { MoreHorizontal, Eye, Ban, Shield } from "lucide-react";
import { ColumnDef } from "@tanstack/react-table";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PageHeader } from "@/components/composed/page-header";
import { DataTable } from "@/components/composed/data-table/data-table";
import type { User } from "@/types/tenant";

// Mock data with org info
const mockUsers: (User & { org_name: string })[] = [
  {
    id: "1",
    email: "admin@acme.com",
    name: "Admin User",
    org_id: "org1",
    org_name: "Acme Corporation",
    roles: ["admin"],
    status: "active",
    created_at: "2024-01-15T00:00:00Z",
    updated_at: "2024-01-15T00:00:00Z",
  },
  {
    id: "2",
    email: "user@techstart.com",
    name: "Tech User",
    org_id: "org2",
    org_name: "TechStart Inc",
    roles: ["member"],
    status: "active",
    created_at: "2024-02-01T00:00:00Z",
    updated_at: "2024-02-01T00:00:00Z",
  },
  {
    id: "3",
    email: "platform@example.com",
    name: "Platform Admin",
    org_id: "org1",
    org_name: "Acme Corporation",
    roles: ["platform_admin"],
    status: "active",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
];

const columns: ColumnDef<(typeof mockUsers)[0]>[] = [
  {
    accessorKey: "name",
    header: "User",
    cell: ({ row }) => (
      <div>
        <div className="font-medium">{row.original.name}</div>
        <div className="text-sm text-muted-foreground">
          {row.original.email}
        </div>
      </div>
    ),
  },
  {
    accessorKey: "org_name",
    header: "Organization",
    cell: ({ row }) => (
      <span className="text-sm">{row.original.org_name}</span>
    ),
  },
  {
    accessorKey: "roles",
    header: "Roles",
    cell: ({ row }) => (
      <div className="flex gap-1">
        {row.original.roles.map((role) => (
          <Badge
            key={role}
            variant={role.includes("admin") ? "default" : "secondary"}
          >
            {role}
          </Badge>
        ))}
      </div>
    ),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => (
      <Badge
        variant={row.original.status === "active" ? "default" : "destructive"}
      >
        {row.original.status}
      </Badge>
    ),
  },
  {
    accessorKey: "created_at",
    header: "Joined",
    cell: ({ row }) =>
      new Date(row.original.created_at).toLocaleDateString(),
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
          <DropdownMenuItem>
            <Eye className="mr-2 h-4 w-4" />
            View Details
          </DropdownMenuItem>
          <DropdownMenuItem>
            <Shield className="mr-2 h-4 w-4" />
            Manage Roles
          </DropdownMenuItem>
          <DropdownMenuItem className="text-destructive">
            <Ban className="mr-2 h-4 w-4" />
            Suspend User
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    ),
  },
];

export default function PlatformUsersPage() {
  const [users] = useState(mockUsers);
  const [search, setSearch] = useState("");

  const filteredUsers = users.filter(
    (user) =>
      user.name.toLowerCase().includes(search.toLowerCase()) ||
      user.email.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Users"
        description="Manage all users across the platform"
      />

      <div className="flex items-center gap-4">
        <Input
          placeholder="Search users..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />
      </div>

      <DataTable
        columns={columns}
        data={filteredUsers}
        emptyState={{
          title: "No users found",
          description: search
            ? "Try adjusting your search."
            : "No users on the platform yet.",
        }}
      />
    </div>
  );
}
