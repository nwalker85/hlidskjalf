"use client";

import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/hooks/use-toast";
import type { User, UpdateUserRequest, UpdateUserRolesRequest } from "@/types/tenant";

const editSchema = z.object({
  full_name: z.string().optional(),
  username: z.string().optional(),
  is_active: z.boolean(),
  role: z.enum(["admin", "member", "viewer"]),
});

type EditFormData = z.infer<typeof editSchema>;

interface EditUserDialogProps {
  user: User | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdate: (userId: string, data: UpdateUserRequest) => Promise<void>;
  onUpdateRoles: (userId: string, data: UpdateUserRolesRequest) => Promise<void>;
}

export function EditUserDialog({
  user,
  open,
  onOpenChange,
  onUpdate,
  onUpdateRoles,
}: EditUserDialogProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { toast } = useToast();

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<EditFormData>({
    resolver: zodResolver(editSchema),
    defaultValues: {
      full_name: "",
      username: "",
      is_active: true,
      role: "member",
    },
  });

  const isActive = watch("is_active");

  useEffect(() => {
    if (user) {
      reset({
        full_name: user.full_name || "",
        username: user.username || "",
        is_active: user.is_active,
        role: (user.roles[0] as "admin" | "member" | "viewer") || "member",
      });
    }
  }, [user, reset]);

  const onSubmit = async (data: EditFormData) => {
    if (!user) return;

    setIsSubmitting(true);
    try {
      // Update user details
      await onUpdate(user.id, {
        full_name: data.full_name || undefined,
        username: data.username || undefined,
        is_active: data.is_active,
      });

      // Update roles if changed
      const currentRole = user.roles[0];
      if (currentRole !== data.role) {
        await onUpdateRoles(user.id, { roles: [data.role] });
      }

      toast({
        title: "User updated",
        description: "User details have been saved successfully.",
      });
      onOpenChange(false);
    } catch (error) {
      toast({
        title: "Failed to update user",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!user) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Edit User</DialogTitle>
          <DialogDescription>
            Update user details and permissions.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" value={user.email} disabled />
              <p className="text-xs text-muted-foreground">
                Email cannot be changed
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="full_name">Name</Label>
              <Input id="full_name" {...register("full_name")} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="username">Username</Label>
              <Input id="username" {...register("username")} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="role">Role</Label>
              <Select
                value={watch("role")}
                onValueChange={(value) =>
                  setValue("role", value as "admin" | "member" | "viewer")
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a role" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Admin</SelectItem>
                  <SelectItem value="member">Member</SelectItem>
                  <SelectItem value="viewer">Viewer</SelectItem>
                </SelectContent>
              </Select>
              {errors.role && (
                <p className="text-sm text-destructive">{errors.role.message}</p>
              )}
            </div>
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="is_active">Active</Label>
                <p className="text-xs text-muted-foreground">
                  Inactive users cannot sign in
                </p>
              </div>
              <Switch
                id="is_active"
                checked={isActive}
                onCheckedChange={(checked) => setValue("is_active", checked)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Changes
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
