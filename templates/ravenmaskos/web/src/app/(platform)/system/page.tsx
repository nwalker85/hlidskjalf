"use client";

import { Save, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { PageHeader } from "@/components/composed/page-header";
import { useToast } from "@/hooks/use-toast";

export default function SystemConfigPage() {
  const { toast } = useToast();

  const handleSave = () => {
    toast({
      title: "Configuration saved",
      description: "System configuration has been updated.",
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="System Configuration"
        description="Platform-wide settings and configuration"
      >
        <Button variant="outline">
          <RefreshCw className="mr-2 h-4 w-4" />
          Reload Config
        </Button>
      </PageHeader>

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Authentication</CardTitle>
            <CardDescription>
              Configure authentication settings
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label>Require MFA</Label>
                <p className="text-sm text-muted-foreground">
                  Require multi-factor authentication for all users
                </p>
              </div>
              <Switch />
            </div>
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label>Allow Registration</Label>
                <p className="text-sm text-muted-foreground">
                  Allow new users to register
                </p>
              </div>
              <Switch defaultChecked />
            </div>
            <div className="space-y-2">
              <Label htmlFor="session-timeout">Session Timeout (minutes)</Label>
              <Input
                id="session-timeout"
                type="number"
                defaultValue="60"
                className="max-w-[200px]"
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Rate Limiting</CardTitle>
            <CardDescription>
              Configure API rate limits
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="rate-limit">Requests per minute (per user)</Label>
              <Input
                id="rate-limit"
                type="number"
                defaultValue="100"
                className="max-w-[200px]"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="burst-limit">Burst limit</Label>
              <Input
                id="burst-limit"
                type="number"
                defaultValue="20"
                className="max-w-[200px]"
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Maintenance</CardTitle>
            <CardDescription>
              Maintenance mode and system status
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label>Maintenance Mode</Label>
                <p className="text-sm text-muted-foreground">
                  Put the platform in maintenance mode
                </p>
              </div>
              <Switch />
            </div>
            <div className="space-y-2">
              <Label htmlFor="maintenance-msg">Maintenance Message</Label>
              <Input
                id="maintenance-msg"
                placeholder="System is under maintenance..."
              />
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button onClick={handleSave}>
            <Save className="mr-2 h-4 w-4" />
            Save Configuration
          </Button>
        </div>
      </div>
    </div>
  );
}
