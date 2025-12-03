"use client";

import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, Shield } from "lucide-react";

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
import { loginSchema, type LoginFormData } from "@/lib/validations/auth";
import type { CurrentUser } from "@/types/auth";

const ZITADEL_ENABLED = !!process.env.NEXT_PUBLIC_ZITADEL_CLIENT_ID;

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const { setAccessToken, setUser } = useAuthStore();
  const [isLoading, setIsLoading] = useState(false);
  const [isOidcLoading, setIsOidcLoading] = useState(false);

  const redirect = searchParams.get("redirect") || "/select-org";
  const error = searchParams.get("error");

  // Show error from OIDC callback
  useEffect(() => {
    if (error) {
      toast({
        title: "Login failed",
        description: decodeURIComponent(error),
        variant: "destructive",
      });
    }
  }, [error, toast]);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginFormData) => {
    setIsLoading(true);
    try {
      // Call BFF login endpoint
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
        credentials: "include",
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message || "Login failed");
      }

      const { access_token } = await response.json();
      setAccessToken(access_token);

      // Fetch user data
      const user = await apiClient.get<CurrentUser>("/auth/me");
      setUser(user);

      toast({
        title: "Welcome back!",
        description: "You have been logged in successfully.",
      });

      router.push(redirect);
    } catch (error) {
      toast({
        title: "Login failed",
        description:
          error instanceof Error ? error.message : "Please check your credentials.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleOidcLogin = async () => {
    setIsOidcLoading(true);
    try {
      // Dynamic import to avoid issues with SSR
      const { generatePKCEChallenge, getZitadelConfig } = await import("@/lib/auth/zitadel");

      const config = getZitadelConfig();
      const pkce = await generatePKCEChallenge();

      // Store PKCE verifier in a cookie for the callback
      document.cookie = `code_verifier=${pkce.codeVerifier}; path=/; max-age=600; samesite=lax`;
      document.cookie = `oauth_state=${pkce.state}; path=/; max-age=600; samesite=lax`;

      // Build authorization URL
      const params = new URLSearchParams({
        client_id: config.clientId,
        redirect_uri: config.redirectUri,
        response_type: "code",
        scope: "openid profile email urn:zitadel:iam:org:project:id:zitadel:aud",
        state: pkce.state,
        code_challenge: pkce.codeChallenge,
        code_challenge_method: "S256",
      });

      // Redirect to Zitadel
      window.location.href = `${config.authorizationEndpoint}?${params.toString()}`;
    } catch (error) {
      console.error("OIDC login error:", error);
      toast({
        title: "Login failed",
        description: "Failed to initiate OIDC login",
        variant: "destructive",
      });
      setIsOidcLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader className="space-y-1">
        <CardTitle className="text-2xl text-center">Sign in</CardTitle>
        <CardDescription className="text-center">
          {ZITADEL_ENABLED
            ? "Sign in with your organization account"
            : "Enter your email and password to sign in"}
        </CardDescription>
      </CardHeader>

      {ZITADEL_ENABLED && (
        <CardContent className="pb-4">
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={handleOidcLogin}
            disabled={isOidcLoading}
          >
            {isOidcLoading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Shield className="mr-2 h-4 w-4" />
            )}
            Continue with SSO
          </Button>
          <div className="relative my-4">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">
                Or continue with email
              </span>
            </div>
          </div>
        </CardContent>
      )}

      <form onSubmit={handleSubmit(onSubmit)}>
        <CardContent className={`space-y-4 ${ZITADEL_ENABLED ? "pt-0" : ""}`}>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              placeholder="name@example.com"
              autoComplete="email"
              disabled={isLoading}
              {...register("email")}
            />
            {errors.email && (
              <p className="text-sm text-destructive">{errors.email.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="password">Password</Label>
              <Link
                href="/forgot-password"
                className="text-sm text-muted-foreground hover:text-primary"
              >
                Forgot password?
              </Link>
            </div>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              disabled={isLoading}
              {...register("password")}
            />
            {errors.password && (
              <p className="text-sm text-destructive">
                {errors.password.message}
              </p>
            )}
          </div>
        </CardContent>
        <CardFooter className="flex flex-col space-y-4">
          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Sign in
          </Button>
          <p className="text-sm text-muted-foreground text-center">
            Don&apos;t have an account?{" "}
            <Link href="/register" className="text-primary hover:underline">
              Sign up
            </Link>
          </p>
        </CardFooter>
      </form>
    </Card>
  );
}
