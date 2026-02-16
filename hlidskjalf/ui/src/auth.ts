import NextAuth from "next-auth";
import type { NextAuthConfig } from "next-auth";

// Multi-environment Zitadel issuer detection
// Supports: .test (dev), .dev (staging), .ai (production)
function getZitadelIssuer(): string {
  // Allow explicit override
  if (process.env.AUTH_ZITADEL_ISSUER) {
    return process.env.AUTH_ZITADEL_ISSUER;
  }
  
  // Detect from NEXTAUTH_URL if available
  const nextAuthUrl = process.env.NEXTAUTH_URL;
  if (nextAuthUrl) {
    if (nextAuthUrl.includes('.dev')) {
      return 'https://zitadel.ravenhelm.dev';
    } else if (nextAuthUrl.includes('.ai')) {
      return 'https://zitadel.ravenhelm.ai';
    }
  }
  
  // Default to dev (.test)
  return 'https://zitadel.ravenhelm.test';
}

// Zitadel OIDC provider configuration
const config: NextAuthConfig = {
  providers: [
    {
      id: "zitadel",
      name: "Zitadel",
      type: "oidc",
      issuer: getZitadelIssuer(),
      clientId: process.env.AUTH_ZITADEL_CLIENT_ID!,
      clientSecret: process.env.AUTH_ZITADEL_CLIENT_SECRET!,
      authorization: {
        params: {
          scope: "openid profile email urn:zitadel:iam:org:project:roles",
        },
      },
      // Zitadel returns roles in urn:zitadel:iam:org:project:roles claim
      profile(profile) {
        return {
          id: profile.sub,
          name: profile.name || profile.preferred_username,
          email: profile.email,
          image: profile.picture,
          // Extract roles from Zitadel's custom claim
          roles: profile["urn:zitadel:iam:org:project:roles"] || {},
        };
      },
    },
  ],
  callbacks: {
    authorized({ auth, request: { nextUrl } }) {
      const isLoggedIn = !!auth?.user;
      const isPublicPath = nextUrl.pathname === "/login";
      
      if (isPublicPath) {
        return true;
      }
      
      if (!isLoggedIn) {
        return false; // Redirect to login
      }
      
      return true;
    },
    jwt({ token, profile }) {
      if (profile) {
        // Store roles in the JWT token
        token.roles = profile["urn:zitadel:iam:org:project:roles"] || {};
      }
      return token;
    },
    session({ session, token }) {
      // Add roles to session
      if (token.roles) {
        (session.user as any).roles = token.roles;
      }
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
  trustHost: true,
  // Debug in development
  debug: process.env.NODE_ENV === "development",
};

export const { handlers, auth, signIn, signOut } = NextAuth(config);

