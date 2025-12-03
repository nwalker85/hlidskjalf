"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { useAuthStore } from "@/stores/auth-store";
import { apiClient } from "@/lib/api/client";
import { mfaSchema, type MFAFormData } from "@/lib/validations/auth";
import type { CurrentUser, AuthTokens } from "@/types/auth";

export function MFAContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const { setAccessToken, setUser } = useAuthStore();
  const [isLoading, setIsLoading] = useState(false);

  const redirect = searchParams.get("redirect") || "/select-org";
  const mfaToken = searchParams.get("mfa_token");

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<MFAFormData>({
    resolver: zodResolver(mfaSchema),
  });

  const onSubmit = async (data: MFAFormData) => {
    if (!mfaToken) {
      toast({
        title: "Invalid session",
        description: "Please start the login process again.",
        variant: "destructive",
      });
      router.push("/login");
      return;
    }

    setIsLoading(true);
    try {
      const tokens = await apiClient.post<AuthTokens>(
        "/auth/mfa/verify",
        {
          mfa_token: mfaToken,
          code: data.code,
        },
        { skipAuth: true }
      );

      setAccessToken(tokens.access_token);

      // Fetch user data
      const user = await apiClient.get<CurrentUser>("/auth/me");
      setUser(user);

      toast({
        title: "Verified!",
        description: "MFA verification successful.",
      });

      router.push(redirect);
    } catch (error) {
      toast({
        title: "Verification failed",
        description:
          error instanceof Error
            ? error.message
            : "Invalid code. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  if (!mfaToken) {
    return (
      <Card>
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl text-center">Session expired</CardTitle>
          <CardDescription className="text-center">
            Your MFA session has expired. Please sign in again.
          </CardDescription>
        </CardHeader>
        <CardFooter>
          <Button className="w-full" onClick={() => router.push("/login")}>
            Go to login
          </Button>
        </CardFooter>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="space-y-1">
        <CardTitle className="text-2xl text-center">
          Two-factor authentication
        </CardTitle>
        <CardDescription className="text-center">
          Enter the 6-digit code from your authenticator app
        </CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit(onSubmit)}>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="code">Authentication Code</Label>
            <Input
              id="code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="000000"
              maxLength={6}
              disabled={isLoading}
              className="text-center text-2xl tracking-widest"
              {...register("code")}
            />
            {errors.code && (
              <p className="text-sm text-destructive">{errors.code.message}</p>
            )}
          </div>
        </CardContent>
        <CardFooter className="flex flex-col space-y-4">
          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Verify
          </Button>
          <p className="text-sm text-muted-foreground text-center">
            Lost your authenticator?{" "}
            <button
              type="button"
              className="text-primary hover:underline"
              onClick={() => {
                toast({
                  title: "Contact support",
                  description:
                    "Please contact your administrator to reset MFA.",
                });
              }}
            >
              Use recovery code
            </button>
          </p>
        </CardFooter>
      </form>
    </Card>
  );
}
