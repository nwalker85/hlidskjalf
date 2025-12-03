"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { CheckCircle, XCircle, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";

export function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"loading" | "success" | "error">(
    "loading"
  );

  const token = searchParams.get("token");

  useEffect(() => {
    const verifyEmail = async () => {
      if (!token) {
        setStatus("error");
        return;
      }

      try {
        await apiClient.post(
          "/auth/verify-email",
          { token },
          { skipAuth: true }
        );
        setStatus("success");
      } catch {
        setStatus("error");
      }
    };

    verifyEmail();
  }, [token]);

  if (status === "loading") {
    return (
      <Card>
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl text-center">
            Verifying your email
          </CardTitle>
          <CardDescription className="text-center">
            Please wait while we verify your email address...
          </CardDescription>
        </CardHeader>
        <CardContent className="flex justify-center py-8">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (status === "success") {
    return (
      <Card>
        <CardHeader className="space-y-1">
          <div className="flex justify-center mb-4">
            <CheckCircle className="h-12 w-12 text-green-500" />
          </div>
          <CardTitle className="text-2xl text-center">Email verified!</CardTitle>
          <CardDescription className="text-center">
            Your email has been verified. You can now sign in to your account.
          </CardDescription>
        </CardHeader>
        <CardFooter>
          <Link href="/login" className="w-full">
            <Button className="w-full">Sign in</Button>
          </Link>
        </CardFooter>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="space-y-1">
        <div className="flex justify-center mb-4">
          <XCircle className="h-12 w-12 text-destructive" />
        </div>
        <CardTitle className="text-2xl text-center">Verification failed</CardTitle>
        <CardDescription className="text-center">
          This verification link is invalid or has expired.
        </CardDescription>
      </CardHeader>
      <CardFooter className="flex flex-col space-y-4">
        <Link href="/login" className="w-full">
          <Button className="w-full">Go to login</Button>
        </Link>
        <p className="text-sm text-muted-foreground text-center">
          Need a new verification link? Sign in and request a new one from your
          settings.
        </p>
      </CardFooter>
    </Card>
  );
}
