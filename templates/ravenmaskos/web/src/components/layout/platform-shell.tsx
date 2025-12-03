"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { PlatformSidebar } from "./sidebar/platform-sidebar";
import { PlatformHeader } from "./header/platform-header";

interface PlatformShellProps {
  children: React.ReactNode;
}

export function PlatformShell({ children }: PlatformShellProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <PlatformSidebar
        collapsed={sidebarCollapsed}
        onCollapsedChange={setSidebarCollapsed}
      />
      <div className="flex flex-1 flex-col overflow-hidden">
        <PlatformHeader
          onMenuClick={() => setSidebarCollapsed(!sidebarCollapsed)}
        />
        <main
          className={cn(
            "flex-1 overflow-auto p-6",
            "transition-all duration-200"
          )}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
