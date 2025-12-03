"use client";

import { useState, useEffect } from "react";
import { Save, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { PageHeader } from "@/components/composed/page-header";
import { StatCard } from "@/components/composed/stat-card";
import { useOrganization } from "@/hooks/use-organization";
import { useToast } from "@/hooks/use-toast";

export default function SettingsPage() {
  const { toast } = useToast();
  const {
    organization,
    stats,
    isLoading,
    error,
    fetchOrganization,
    fetchStats,
    updateOrganization,
  } = useOrganization();

  const [orgName, setOrgName] = useState("");
  const [orgDescription, setOrgDescription] = useState("");
  const [orgDomain, setOrgDomain] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    fetchOrganization();
    fetchStats();
  }, [fetchOrganization, fetchStats]);

  useEffect(() => {
    if (organization) {
      setOrgName(organization.name);
      setOrgDescription(organization.description || "");
      setOrgDomain(organization.domain || "");
    }
  }, [organization]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await updateOrganization({
        name: orgName,
        description: orgDescription || undefined,
        domain: orgDomain || undefined,
      });
      toast({
        title: "Settings saved",
        description: "Organization settings have been updated.",
      });
    } catch (err) {
      toast({
        title: "Failed to save",
        description: err instanceof Error ? err.message : "Please try again",
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title="Settings" description="Manage organization settings" />
        <div className="space-y-6">
          <Skeleton className="h-[200px] w-full" />
          <Skeleton className="h-[150px] w-full" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Manage organization settings"
      />

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {stats && (
        <div className="grid gap-4 md:grid-cols-3">
          <StatCard
            title="Users"
            value={stats.user_count}
            description="Active members"
          />
          <StatCard
            title="API Keys"
            value={stats.api_key_count}
            description="Active keys"
          />
          <StatCard
            title="Plan"
            value={stats.tier.charAt(0).toUpperCase() + stats.tier.slice(1)}
            description={stats.is_active ? "Active" : "Inactive"}
          />
        </div>
      )}

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>General</CardTitle>
            <CardDescription>
              Basic organization information
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="orgName">Organization Name</Label>
              <Input
                id="orgName"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                placeholder="Acme Corp"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="orgSlug">URL Slug</Label>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">
                  ravenmaskos.app/
                </span>
                <Input
                  id="orgSlug"
                  value={organization?.slug || ""}
                  disabled
                  className="max-w-[200px] bg-muted"
                />
              </div>
              <p className="text-xs text-muted-foreground">
                URL slug cannot be changed after creation
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="orgDescription">Description</Label>
              <Input
                id="orgDescription"
                value={orgDescription}
                onChange={(e) => setOrgDescription(e.target.value)}
                placeholder="A brief description of your organization"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="orgDomain">Custom Domain</Label>
              <Input
                id="orgDomain"
                value={orgDomain}
                onChange={(e) => setOrgDomain(e.target.value)}
                placeholder="acme.com"
              />
              <p className="text-xs text-muted-foreground">
                Used for SSO and email domain verification
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Danger Zone</CardTitle>
            <CardDescription>
              Irreversible actions for your organization
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between p-4 rounded-lg border border-destructive/20 bg-destructive/5">
              <div>
                <h4 className="font-medium">Delete Organization</h4>
                <p className="text-sm text-muted-foreground">
                  Permanently delete this organization and all its data
                </p>
              </div>
              <Button variant="destructive">Delete</Button>
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            Save Changes
          </Button>
        </div>
      </div>
    </div>
  );
}
