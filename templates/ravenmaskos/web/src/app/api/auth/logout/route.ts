import { NextRequest, NextResponse } from "next/server";

const ZITADEL_ISSUER = process.env.NEXT_PUBLIC_ZITADEL_ISSUER || "http://localhost:8085";
const ZITADEL_CLIENT_ID = process.env.NEXT_PUBLIC_ZITADEL_CLIENT_ID || "";

export async function POST(request: NextRequest) {
  const res = NextResponse.json({ success: true });

  // Clear all auth cookies
  res.cookies.set("refresh_token", "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });

  res.cookies.set("access_token", "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });

  res.cookies.set("id_token", "", {
    httpOnly: false,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });

  return res;
}

// GET endpoint for Zitadel logout redirect
export async function GET(request: NextRequest) {
  // Build Zitadel end_session URL
  const postLogoutRedirectUri = request.nextUrl.origin;
  const idToken = request.cookies.get("id_token")?.value;

  const params = new URLSearchParams({
    client_id: ZITADEL_CLIENT_ID,
    post_logout_redirect_uri: postLogoutRedirectUri,
  });

  if (idToken) {
    params.set("id_token_hint", idToken);
  }

  const logoutUrl = `${ZITADEL_ISSUER}/oidc/v1/end_session?${params.toString()}`;

  // Clear cookies and redirect
  const response = NextResponse.redirect(logoutUrl);

  response.cookies.set("refresh_token", "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });

  response.cookies.set("access_token", "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });

  response.cookies.set("id_token", "", {
    httpOnly: false,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });

  return response;
}
