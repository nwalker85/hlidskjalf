"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useTenant } from "@/providers/tenant-provider";
import {
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
  Users,
  Shield,
  Key,
  ScrollText,
  Settings,
  Building2,
} from "lucide-react";

interface SidebarProps {
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
}

interface NavItem {
  title: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

export function Sidebar({ collapsed, onCollapsedChange }: SidebarProps) {
  const pathname = usePathname();
  const { currentOrg } = useTenant();

  const orgSlug = currentOrg?.slug || "";

  const navItems: NavItem[] = [
    {
      title: "Dashboard",
      href: `/${orgSlug}`,
      icon: LayoutDashboard,
    },
    {
      title: "Users",
      href: `/${orgSlug}/users`,
      icon: Users,
    },
    {
      title: "Roles",
      href: `/${orgSlug}/roles`,
      icon: Shield,
    },
    {
      title: "API Keys",
      href: `/${orgSlug}/api-keys`,
      icon: Key,
    },
    {
      title: "Audit Log",
      href: `/${orgSlug}/audit-log`,
      icon: ScrollText,
    },
  ];

  const settingsItems: NavItem[] = [
    {
      title: "Settings",
      href: `/${orgSlug}/settings`,
      icon: Settings,
    },
  ];

  return (
    <aside
      className={cn(
        "flex flex-col border-r bg-card transition-all duration-200",
        collapsed ? "w-16" : "w-64"
      )}
    >
      {/* Logo/Brand */}
      <div className="flex h-16 items-center justify-between px-4 border-b">
        {!collapsed && (
          <Link href={`/${orgSlug}`} className="flex items-center gap-2">
            <Building2 className="h-6 w-6 text-primary" />
            <span className="font-semibold text-lg truncate">
              {currentOrg?.name || "RavenMaskOS"}
            </span>
          </Link>
        )}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onCollapsedChange(!collapsed)}
          className={cn(collapsed && "mx-auto")}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </Button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-2">
        {navItems.map((item) => (
          <NavLink
            key={item.href}
            item={item}
            collapsed={collapsed}
            isActive={pathname === item.href}
          />
        ))}

        <Separator className="my-4" />

        {settingsItems.map((item) => (
          <NavLink
            key={item.href}
            item={item}
            collapsed={collapsed}
            isActive={pathname === item.href}
          />
        ))}
      </nav>
    </aside>
  );
}

interface NavLinkProps {
  item: NavItem;
  collapsed: boolean;
  isActive: boolean;
}

function NavLink({ item, collapsed, isActive }: NavLinkProps) {
  const Icon = item.icon;

  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
        isActive
          ? "bg-primary text-primary-foreground"
          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
        collapsed && "justify-center px-2"
      )}
    >
      <Icon className="h-5 w-5 shrink-0" />
      {!collapsed && <span className="truncate">{item.title}</span>}
    </Link>
  );
}
