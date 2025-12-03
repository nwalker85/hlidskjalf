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
import type { User } from "@/types/tenant";

interface DeleteUserDialogProps {
  user: User | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDelete: (userId: string) => Promise<void>;
}

export function DeleteUserDialog({
  user,
  open,
  onOpenChange,
  onDelete,
}: DeleteUserDialogProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const { toast } = useToast();

  const handleDelete = async () => {
    if (!user) return;

    setIsDeleting(true);
    try {
      await onDelete(user.id);
      toast({
        title: "User removed",
        description: `${user.email} has been removed from the organization.`,
      });
      onOpenChange(false);
    } catch (error) {
      toast({
        title: "Failed to remove user",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
    } finally {
      setIsDeleting(false);
    }
  };

  if (!user) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            Remove User
          </DialogTitle>
          <DialogDescription>
            Are you sure you want to remove this user from your organization?
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <div className="rounded-lg border p-4">
            <p className="font-medium">{user.full_name || user.email}</p>
            <p className="text-sm text-muted-foreground">{user.email}</p>
          </div>
          <p className="mt-4 text-sm text-muted-foreground">
            This action will revoke the user&apos;s access to all organization
            resources. They will no longer be able to sign in or access any data.
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
            onClick={handleDelete}
            disabled={isDeleting}
          >
            {isDeleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Remove User
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
