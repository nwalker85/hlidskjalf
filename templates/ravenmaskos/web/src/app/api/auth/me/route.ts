import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.API_URL || "http://localhost:8000";

export async function GET(request: NextRequest) {
  try {
    // Try Authorization header first (client-side token)
    let authHeader = request.headers.get("authorization");

    // Fall back to HttpOnly cookie (OIDC flow)
    if (!authHeader) {
      const accessToken = request.cookies.get("access_token")?.value;
      if (accessToken) {
        authHeader = `Bearer ${accessToken}`;
      }
    }

    if (!authHeader) {
      return NextResponse.json(
        { message: "No authorization header" },
        { status: 401 }
      );
    }

    // Forward request to backend
    const response = await fetch(`${API_URL}/auth/me`, {
      method: "GET",
      headers: {
        Authorization: authHeader,
      },
    });

    if (!response.ok) {
      return NextResponse.json(
        { message: "Unauthorized" },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Get user error:", error);
    return NextResponse.json(
      { message: "Internal server error" },
      { status: 500 }
    );
  }
}
