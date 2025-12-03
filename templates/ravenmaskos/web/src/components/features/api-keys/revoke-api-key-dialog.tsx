"use client";

import { useState } from "react";
import { Loader2, AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import type { ApiKey } from "@/types/tenant";

interface RevokeApiKeyDialogProps {
  apiKey: ApiKey | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRevoke: (keyId: string) => Promise<void>;
}

export function RevokeApiKeyDialog({
  apiKey,
  open,
  onOpenChange,
  onRevoke,
}: RevokeApiKeyDialogProps) {
  const [isRevoking, setIsRevoking] = useState(false);
  const { toast } = useToast();

  const handleRevoke = async () => {
    if (!apiKey) return;

    setIsRevoking(true);
    try {
      await onRevoke(apiKey.id);
      toast({
        title: "API key revoked",
        description: `${apiKey.name} has been revoked and can no longer be used.`,
      });
      onOpenChange(false);
    } catch (error) {
      toast({
        title: "Failed to revoke API key",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
    } finally {
      setIsRevoking(false);
    }
  };

  if (!apiKey) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            Revoke API Key
          </DialogTitle>
          <DialogDescription>
            Are you sure you want to revoke this API key?
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <div className="rounded-lg border p-4">
            <p className="font-medium">{apiKey.name}</p>
            <p className="text-sm text-muted-foreground">
              Prefix: {apiKey.key_prefix}...
            </p>
            {apiKey.description && (
              <p className="mt-1 text-sm text-muted-foreground">
                {apiKey.description}
              </p>
            )}
          </div>
          <p className="mt-4 text-sm text-muted-foreground">
            This action cannot be undone. Any applications using this key will
            immediately lose access.
          </p>
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleRevoke}
            disabled={isRevoking}
          >
            {isRevoking && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Revoke Key
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
