"use client";

import { useState, useEffect } from "react";
import { Mail, MoreHorizontal, Pencil, Trash2, Search } from "lucide-react";
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
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/composed/page-header";
import { DataTable } from "@/components/composed/data-table/data-table";
import {
  InviteUserDialog,
  EditUserDialog,
  DeleteUserDialog,
} from "@/components/features/users";
import { useUsers } from "@/hooks/use-users";
import type { User } from "@/types/tenant";

export default function UsersPage() {
  const {
    users,
    isLoading,
    error,
    fetchUsers,
    inviteUser,
    updateUser,
    updateUserRoles,
    deleteUser,
  } = useUsers();

  const [search, setSearch] = useState("");
  const [inviteDialogOpen, setInviteDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  useEffect(() => {
    const debounce = setTimeout(() => {
      fetchUsers({ search: search || undefined });
    }, 300);
    return () => clearTimeout(debounce);
  }, [search, fetchUsers]);

  const handleEdit = (user: User) => {
    setSelectedUser(user);
    setEditDialogOpen(true);
  };

  const handleDelete = (user: User) => {
    setSelectedUser(user);
    setDeleteDialogOpen(true);
  };

  const columns: ColumnDef<User>[] = [
    {
      accessorKey: "full_name",
      header: "Name",
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center text-sm font-medium">
            {(row.original.full_name || row.original.email)[0].toUpperCase()}
          </div>
          <div>
            <div className="font-medium">
              {row.original.full_name || "No name"}
            </div>
            <div className="text-sm text-muted-foreground">
              {row.original.email}
            </div>
          </div>
        </div>
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
              variant={role === "admin" ? "default" : "secondary"}
            >
              {role}
            </Badge>
          ))}
        </div>
      ),
    },
    {
      accessorKey: "is_active",
      header: "Status",
      cell: ({ row }) => {
        const isActive = row.original.is_active;
        const isVerified = row.original.is_verified;

        if (!isActive) {
          return <Badge variant="destructive">Inactive</Badge>;
        }
        if (!isVerified) {
          return <Badge variant="secondary">Pending</Badge>;
        }
        return <Badge variant="default">Active</Badge>;
      },
    },
    {
      accessorKey: "last_login_at",
      header: "Last Login",
      cell: ({ row }) => {
        const lastLogin = row.original.last_login_at;
        if (!lastLogin) return <span className="text-muted-foreground">Never</span>;
        return new Date(lastLogin).toLocaleDateString();
      },
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
            <DropdownMenuItem onClick={() => handleEdit(row.original)}>
              <Pencil className="mr-2 h-4 w-4" />
              Edit
            </DropdownMenuItem>
            <DropdownMenuItem
              className="text-destructive"
              onClick={() => handleDelete(row.original)}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Remove
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ];

  if (isLoading && users.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader title="Users" description="Manage organization members">
          <Button disabled>
            <Mail className="mr-2 h-4 w-4" />
            Invite User
          </Button>
        </PageHeader>
        <div className="space-y-4">
          <Skeleton className="h-10 w-[300px]" />
          <Skeleton className="h-[400px] w-full" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Users" description="Manage organization members">
        <Button onClick={() => setInviteDialogOpen(true)}>
          <Mail className="mr-2 h-4 w-4" />
          Invite User
        </Button>
      </PageHeader>

      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search users..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      <DataTable
        columns={columns}
        data={users}
        emptyState={{
          title: "No users",
          description: "Invite team members to get started.",
        }}
      />

      <InviteUserDialog
        open={inviteDialogOpen}
        onOpenChange={setInviteDialogOpen}
        onInvite={inviteUser}
      />

      <EditUserDialog
        user={selectedUser}
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        onUpdate={updateUser}
        onUpdateRoles={updateUserRoles}
      />

      <DeleteUserDialog
        user={selectedUser}
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        onDelete={deleteUser}
      />
    </div>
  );
}
