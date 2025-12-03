"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Copy, Loader2, Eye, EyeOff } from "lucide-react";

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
import { useToast } from "@/hooks/use-toast";
import type { CreateApiKeyRequest, ApiKeyCreated } from "@/types/tenant";

const createSchema = z.object({
  name: z.string().min(1, "Name is required").max(255),
  description: z.string().optional(),
  expires_in_days: z.string().optional(),
});

type CreateFormData = z.infer<typeof createSchema>;

interface CreateApiKeyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreate: (data: CreateApiKeyRequest) => Promise<ApiKeyCreated>;
}

export function CreateApiKeyDialog({
  open,
  onOpenChange,
  onCreate,
}: CreateApiKeyDialogProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createdKey, setCreatedKey] = useState<ApiKeyCreated | null>(null);
  const [showKey, setShowKey] = useState(false);
  const { toast } = useToast();

  const {
    register,
    handleSubmit,
    setValue,
    reset,
    formState: { errors },
  } = useForm<CreateFormData>({
    resolver: zodResolver(createSchema),
    defaultValues: {
      name: "",
      description: "",
      expires_in_days: "never",
    },
  });

  const onSubmit = async (data: CreateFormData) => {
    setIsSubmitting(true);
    try {
      const expiresInDays =
        data.expires_in_days === "never"
          ? undefined
          : parseInt(data.expires_in_days || "0", 10);

      const result = await onCreate({
        name: data.name,
        description: data.description || undefined,
        expires_in_days: expiresInDays,
      });
      setCreatedKey(result);
      toast({
        title: "API key created",
        description: "Make sure to copy your key - it won't be shown again!",
      });
    } catch (error) {
      toast({
        title: "Failed to create API key",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const copyToClipboard = async () => {
    if (createdKey?.key) {
      await navigator.clipboard.writeText(createdKey.key);
      toast({
        title: "Copied to clipboard",
        description: "API key has been copied to your clipboard",
      });
    }
  };

  const handleClose = () => {
    reset();
    setCreatedKey(null);
    setShowKey(false);
    onOpenChange(false);
  };

  // Show key confirmation step
  if (createdKey) {
    return (
      <Dialog open={open} onOpenChange={handleClose}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>API Key Created</DialogTitle>
            <DialogDescription>
              Copy your API key now. You won&apos;t be able to see it again!
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <div className="space-y-4">
              <div>
                <Label>Key Name</Label>
                <p className="text-sm font-medium">{createdKey.name}</p>
              </div>
              <div>
                <Label>API Key</Label>
                <div className="mt-1 flex items-center gap-2">
                  <div className="flex-1 rounded-md border bg-muted p-3 font-mono text-sm break-all">
                    {showKey ? createdKey.key : "•".repeat(40)}
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={() => setShowKey(!showKey)}
                  >
                    {showKey ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={copyToClipboard}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
                This is the only time this key will be displayed. Store it securely
                - you cannot retrieve it later.
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button onClick={handleClose}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Create API Key</DialogTitle>
          <DialogDescription>
            Create a new API key for programmatic access.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                placeholder="My API Key"
                {...register("name")}
              />
              {errors.name && (
                <p className="text-sm text-destructive">{errors.name.message}</p>
              )}
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description">Description (optional)</Label>
              <Input
                id="description"
                placeholder="Used for CI/CD pipeline"
                {...register("description")}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="expires">Expiration</Label>
              <Select
                defaultValue="never"
                onValueChange={(value) => setValue("expires_in_days", value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select expiration" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="never">Never expires</SelectItem>
                  <SelectItem value="30">30 days</SelectItem>
                  <SelectItem value="90">90 days</SelectItem>
                  <SelectItem value="180">180 days</SelectItem>
                  <SelectItem value="365">1 year</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Key
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
