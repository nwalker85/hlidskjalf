import { NextRequest, NextResponse } from "next/server";

const ZITADEL_ISSUER = process.env.NEXT_PUBLIC_ZITADEL_ISSUER || "http://localhost:8085";
const ZITADEL_CLIENT_ID = process.env.NEXT_PUBLIC_ZITADEL_CLIENT_ID || "";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const code = searchParams.get("code");
  const state = searchParams.get("state");
  const error = searchParams.get("error");
  const errorDescription = searchParams.get("error_description");

  // Handle OIDC errors
  if (error) {
    console.error("OIDC error:", error, errorDescription);
    return NextResponse.redirect(
      new URL(`/login?error=${encodeURIComponent(errorDescription || error)}`, request.url)
    );
  }

  if (!code) {
    return NextResponse.redirect(
      new URL("/login?error=missing_code", request.url)
    );
  }

  // Get code_verifier from cookie (set by login page before redirect)
  const codeVerifier = request.cookies.get("code_verifier")?.value;

  if (!codeVerifier) {
    console.error("Missing code_verifier");
    return NextResponse.redirect(
      new URL("/login?error=missing_verifier", request.url)
    );
  }

  try {
    // Exchange code for tokens
    const tokenResponse = await fetch(`${ZITADEL_ISSUER}/oauth/v2/token`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({
        grant_type: "authorization_code",
        client_id: ZITADEL_CLIENT_ID,
        code,
        redirect_uri: `${request.nextUrl.origin}/api/auth/callback`,
        code_verifier: codeVerifier,
      }),
    });

    if (!tokenResponse.ok) {
      const error = await tokenResponse.json().catch(() => ({}));
      console.error("Token exchange failed:", error);
      return NextResponse.redirect(
        new URL(`/login?error=${encodeURIComponent(error.error_description || "token_exchange_failed")}`, request.url)
      );
    }

    const tokens = await tokenResponse.json();

    // Create response redirecting to select-org
    const response = NextResponse.redirect(
      new URL("/select-org", request.url)
    );

    // Store access token in a secure cookie (short-lived)
    response.cookies.set("access_token", tokens.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: tokens.expires_in || 3600,
    });

    // Store refresh token in a secure cookie (long-lived)
    if (tokens.refresh_token) {
      response.cookies.set("refresh_token", tokens.refresh_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
        maxAge: 60 * 60 * 24 * 30, // 30 days
      });
    }

    // Store ID token for userinfo (readable by client for user display)
    if (tokens.id_token) {
      response.cookies.set("id_token", tokens.id_token, {
        httpOnly: false, // Client can read this for user info
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
        maxAge: tokens.expires_in || 3600,
      });
    }

    // Clear the code_verifier cookie
    response.cookies.delete("code_verifier");
    response.cookies.delete("oauth_state");

    return response;
  } catch (error) {
    console.error("Callback error:", error);
    return NextResponse.redirect(
      new URL("/login?error=callback_failed", request.url)
    );
  }
}
