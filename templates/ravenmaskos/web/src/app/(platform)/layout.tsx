"use client";

import { AuthGuard } from "@/components/guards/auth-guard";
import { RoleGuard } from "@/components/guards/role-guard";
import { PlatformShell } from "@/components/layout/platform-shell";

export default function PlatformLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <RoleGuard roles={["platform_admin", "super_admin"]}>
        <PlatformShell>{children}</PlatformShell>
      </RoleGuard>
    </AuthGuard>
  );
}
