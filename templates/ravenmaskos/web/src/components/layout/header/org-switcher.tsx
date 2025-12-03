"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Check, ChevronsUpDown, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useTenant } from "@/providers/tenant-provider";
import type { Organization } from "@/types/tenant";

export function OrgSwitcher() {
  const router = useRouter();
  const { currentOrg, setOrg } = useTenant();
  const [organizations] = useState<Organization[]>([
    // This would normally come from an API call
    // For now, we just show the current org
  ]);

  const handleOrgSelect = (org: Organization) => {
    setOrg(org);
    router.push(`/${org.slug}`);
  };

  if (!currentOrg) {
    return null;
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" className="w-[200px] justify-between">
          <span className="truncate">{currentOrg.name}</span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-[200px]" align="start">
        <DropdownMenuLabel>Organizations</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {organizations.length > 0 ? (
          organizations.map((org) => (
            <DropdownMenuItem
              key={org.id}
              onClick={() => handleOrgSelect(org)}
              className="cursor-pointer"
            >
              <Check
                className={cn(
                  "mr-2 h-4 w-4",
                  currentOrg.id === org.id ? "opacity-100" : "opacity-0"
                )}
              />
              <span className="truncate">{org.name}</span>
            </DropdownMenuItem>
          ))
        ) : (
          <DropdownMenuItem
            onClick={() => handleOrgSelect(currentOrg)}
            className="cursor-pointer"
          >
            <Check className="mr-2 h-4 w-4 opacity-100" />
            <span className="truncate">{currentOrg.name}</span>
          </DropdownMenuItem>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={() => router.push("/select-org")}
          className="cursor-pointer"
        >
          <Plus className="mr-2 h-4 w-4" />
          Switch Organization
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
