import { auth } from "@/auth";

export default auth((req) => {
  const isLoggedIn = !!req.auth;
  const isPublicPath = req.nextUrl.pathname === "/login" || 
                       req.nextUrl.pathname.startsWith("/api/auth");
  
  // Allow public paths
  if (isPublicPath) {
    return;
  }
  
  // Redirect to login if not authenticated
  if (!isLoggedIn) {
    const loginUrl = new URL("/login", req.nextUrl.origin);
    loginUrl.searchParams.set("callbackUrl", req.nextUrl.pathname);
    return Response.redirect(loginUrl);
  }
});

export const config = {
  // Match all paths except static files and api routes (except auth)
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|api/(?!auth)).*)",
  ],
};

