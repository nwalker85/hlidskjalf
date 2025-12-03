"use client";

import { useAuth } from "@/providers/auth-provider";

interface ScopeGuardProps {
  scopes: string[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
  requireAll?: boolean;
}

export function ScopeGuard({
  scopes,
  children,
  fallback = null,
  requireAll = true,
}: ScopeGuardProps) {
  const { hasScope, hasAllScopes, isLoading } = useAuth();

  if (isLoading) {
    return null;
  }

  const hasAccess = requireAll
    ? hasAllScopes(scopes)
    : scopes.some((scope) => hasScope(scope));

  if (!hasAccess) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}
