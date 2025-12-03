"use client";

import { QueryProvider } from "./query-provider";
import { ThemeProvider } from "./theme-provider";
import { AuthProvider } from "./auth-provider";
import { TenantProvider } from "./tenant-provider";
import { Toaster } from "@/components/ui/toaster";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryProvider>
      <ThemeProvider>
        <AuthProvider>
          <TenantProvider>
            {children}
            <Toaster />
          </TenantProvider>
        </AuthProvider>
      </ThemeProvider>
    </QueryProvider>
  );
}
