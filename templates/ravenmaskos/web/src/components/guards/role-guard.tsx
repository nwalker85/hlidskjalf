"use client";

import { useAuth } from "@/providers/auth-provider";

interface RoleGuardProps {
  roles: string[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
  requireAll?: boolean;
}

export function RoleGuard({
  roles,
  children,
  fallback = <AccessDenied />,
  requireAll = false,
}: RoleGuardProps) {
  const { hasRole, hasAnyRole, isLoading } = useAuth();

  if (isLoading) {
    return null;
  }

  const hasAccess = requireAll
    ? roles.every((role) => hasRole(role))
    : hasAnyRole(roles);

  if (!hasAccess) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}

function AccessDenied() {
  return (
    <div className="flex h-full flex-col items-center justify-center p-8">
      <h2 className="text-2xl font-semibold text-foreground">Access Denied</h2>
      <p className="mt-2 text-muted-foreground">
        You don&apos;t have permission to view this content.
      </p>
    </div>
  );
}
