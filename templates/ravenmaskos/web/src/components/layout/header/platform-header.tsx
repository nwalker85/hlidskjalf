"use client";

import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { UserNav } from "./user-nav";
import { ThemeToggle } from "./theme-toggle";
import { Badge } from "@/components/ui/badge";

interface PlatformHeaderProps {
  onMenuClick: () => void;
}

export function PlatformHeader({ onMenuClick }: PlatformHeaderProps) {
  return (
    <header className="flex h-16 items-center justify-between border-b bg-card px-4">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={onMenuClick}
          className="lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </Button>
        <Badge variant="destructive">Platform Admin</Badge>
      </div>

      <div className="flex items-center gap-2">
        <ThemeToggle />
        <UserNav />
      </div>
    </header>
  );
}
