"use client";

import { AuthGuard } from "@/components/guards/auth-guard";
import { AppShell } from "@/components/layout/app-shell";

export default function TenantLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <AppShell>{children}</AppShell>
    </AuthGuard>
  );
}
