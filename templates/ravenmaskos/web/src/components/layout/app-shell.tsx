"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Sidebar } from "./sidebar/sidebar";
import { Header } from "./header/header";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar
        collapsed={sidebarCollapsed}
        onCollapsedChange={setSidebarCollapsed}
      />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header onMenuClick={() => setSidebarCollapsed(!sidebarCollapsed)} />
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
