"use client";

import { useState, useEffect, useMemo } from "react";
import { Shield, Users, Eye, Lock } from "lucide-react";
import { ColumnDef } from "@tanstack/react-table";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { PageHeader } from "@/components/composed/page-header";
import { DataTable } from "@/components/composed/data-table/data-table";
import { Skeleton } from "@/components/ui/skeleton";
import { useUsers } from "@/hooks/use-users";
import type { User } from "@/types/tenant";

// Role definitions from OpenFGA model
interface RoleDefinition {
  name: string;
  description: string;
  icon: React.ReactNode;
  capabilities: string[];
  level: "admin" | "member" | "viewer";
}

const ROLE_DEFINITIONS: RoleDefinition[] = [
  {
    name: "Admin",
    description: "Full access to all organization resources",
    icon: <Shield className="h-5 w-5" />,
    level: "admin",
    capabilities: [
      "Manage organization settings",
      "Invite and remove users",
      "Manage user roles",
      "Create and revoke API keys",
      "View audit logs",
      "Access all resources",
    ],
  },
  {
    name: "Member",
    description: "Standard access to organization resources",
    icon: <Users className="h-5 w-5" />,
    level: "member",
    capabilities: [
      "View organization settings",
      "View other users",
      "View API keys",
      "Create personal resources",
      "Access shared resources",
    ],
  },
  {
    name: "Viewer",
    description: "Read-only access to organization resources",
    icon: <Eye className="h-5 w-5" />,
    level: "viewer",
    capabilities: [
      "View organization info",
      "View shared resources",
      "Read-only access",
    ],
  },
];

interface UsersByRole {
  admin: User[];
  member: User[];
  viewer: User[];
}

export default function RolesPage() {
  const { users, isLoading, fetchUsers } = useUsers();

  useEffect(() => {
    fetchUsers({ page: 1 });
  }, [fetchUsers]);

  // Group users by their primary role
  const usersByRole = useMemo<UsersByRole>(() => {
    const result: UsersByRole = { admin: [], member: [], viewer: [] };

    users.forEach((user) => {
      if (user.roles.includes("admin")) {
        result.admin.push(user);
      } else if (user.roles.includes("member")) {
        result.member.push(user);
      } else if (user.roles.includes("viewer")) {
        result.viewer.push(user);
      }
    });

    return result;
  }, [users]);

  const userColumns: ColumnDef<User>[] = [
    {
      accessorKey: "full_name",
      header: "User",
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
      accessorKey: "is_active",
      header: "Status",
      cell: ({ row }) => (
        <Badge variant={row.original.is_active ? "default" : "secondary"}>
          {row.original.is_active ? "Active" : "Inactive"}
        </Badge>
      ),
    },
  ];

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Roles & Permissions"
          description="View role definitions and assignments"
        />
        <div className="grid gap-6 md:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-[300px]" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Roles & Permissions"
        description="View role definitions and assignments"
      />

      <div className="rounded-lg border bg-muted/50 p-4">
        <div className="flex items-start gap-3">
          <Lock className="h-5 w-5 text-muted-foreground mt-0.5" />
          <div>
            <h3 className="font-medium">Role-Based Access Control</h3>
            <p className="text-sm text-muted-foreground">
              Roles are managed through OpenFGA&apos;s relationship-based authorization
              model. Use the Users page to assign roles to individual users.
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        {ROLE_DEFINITIONS.map((role) => (
          <Card key={role.name}>
            <CardHeader>
              <div className="flex items-center gap-2">
                <div className="rounded-lg bg-primary/10 p-2 text-primary">
                  {role.icon}
                </div>
                <div>
                  <CardTitle className="text-lg">{role.name}</CardTitle>
                  <Badge variant="outline" className="mt-1">
                    {usersByRole[role.level].length} users
                  </Badge>
                </div>
              </div>
              <CardDescription className="mt-2">
                {role.description}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <h4 className="text-sm font-medium mb-2">Capabilities</h4>
                  <ul className="space-y-1">
                    {role.capabilities.map((cap) => (
                      <li
                        key={cap}
                        className="text-sm text-muted-foreground flex items-center gap-2"
                      >
                        <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                        {cap}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="space-y-6">
        {ROLE_DEFINITIONS.map((role) => (
          <Card key={`${role.name}-users`}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {role.icon}
                {role.name}s
              </CardTitle>
              <CardDescription>
                Users with the {role.name.toLowerCase()} role
              </CardDescription>
            </CardHeader>
            <CardContent>
              <DataTable
                columns={userColumns}
                data={usersByRole[role.level]}
                emptyState={{
                  title: `No ${role.name.toLowerCase()}s`,
                  description: `No users have the ${role.name.toLowerCase()} role.`,
                }}
              />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
