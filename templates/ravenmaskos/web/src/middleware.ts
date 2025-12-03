import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Routes that don't require authentication
const publicRoutes = [
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
];

// Routes that require platform admin role (checked client-side)
const platformAdminRoutes = ["/platform"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const refreshToken = request.cookies.get("refresh_token");

  // Skip middleware for API routes, static files, etc.
  if (
    pathname.startsWith("/api") ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/favicon") ||
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }

  // Check if it's a public route
  const isPublicRoute = publicRoutes.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`)
  );

  // Redirect authenticated users away from auth pages
  if (isPublicRoute && refreshToken) {
    // If user is already authenticated, redirect to dashboard
    // We'll redirect to a generic dashboard - the actual org will be selected there
    return NextResponse.redirect(new URL("/select-org", request.url));
  }

  // Redirect unauthenticated users to login
  if (!isPublicRoute && !refreshToken) {
    const loginUrl = new URL("/login", request.url);
    // Save the original URL to redirect back after login
    if (pathname !== "/" && pathname !== "/select-org") {
      loginUrl.searchParams.set("redirect", pathname);
    }
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    "/((?!api|_next/static|_next/image|favicon.ico).*)",
  ],
};
