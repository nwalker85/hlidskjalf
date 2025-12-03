"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Building2, Plus, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/providers/auth-provider";
import { useTenant } from "@/providers/tenant-provider";
import { apiClient } from "@/lib/api/client";
import type { Organization } from "@/types/tenant";
import type { PaginatedResponse } from "@/types/api";

export default function SelectOrgPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { setOrg } = useTenant();
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadOrgs = async () => {
      if (!isAuthenticated) return;

      try {
        const response = await apiClient.get<PaginatedResponse<Organization>>(
          "/organizations"
        );
        setOrganizations(response.items);

        // If user only has one org, redirect directly
        if (response.items.length === 1) {
          const org = response.items[0];
          setOrg(org);
          router.push(`/${org.slug}`);
        }
      } catch (error) {
        console.error("Failed to load organizations:", error);
      } finally {
        setIsLoading(false);
      }
    };

    if (!authLoading) {
      loadOrgs();
    }
  }, [isAuthenticated, authLoading, router, setOrg]);

  const handleSelectOrg = (org: Organization) => {
    setOrg(org);
    router.push(`/${org.slug}`);
  };

  if (authLoading || isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Card className="w-full max-w-md">
          <CardHeader>
            <Skeleton className="h-8 w-48 mx-auto" />
            <Skeleton className="h-4 w-64 mx-auto" />
          </CardHeader>
          <CardContent className="space-y-4">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">Select Organization</CardTitle>
          <CardDescription>
            Choose an organization to continue
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {organizations.length === 0 ? (
            <div className="text-center py-8">
              <Building2 className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground mb-4">
                You don&apos;t belong to any organizations yet.
              </p>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Create Organization
              </Button>
            </div>
          ) : (
            <>
              {organizations.map((org) => (
                <button
                  key={org.id}
                  onClick={() => handleSelectOrg(org)}
                  className="w-full flex items-center gap-4 p-4 rounded-lg border hover:bg-accent transition-colors text-left"
                >
                  <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                    <Building2 className="h-5 w-5 text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{org.name}</p>
                    <p className="text-sm text-muted-foreground truncate">
                      {org.slug}
                    </p>
                  </div>
                </button>
              ))}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
