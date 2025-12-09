import { NextRequest, NextResponse } from "next/server";

// Resolve the control-plane API base URL
const BACKEND_URL =
  process.env.BACKEND_URL ||
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://hlidskjalf:8900";

// GET - List all providers
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const enabledOnly = searchParams.get("enabled_only") === "true";
  
  try {
    const url = new URL("/api/v1/llm/providers", BACKEND_URL);
    if (enabledOnly) {
      url.searchParams.set("enabled_only", "true");
    }
    
    const resp = await fetch(url.toString(), {
      cache: "no-store",
    });
    
    if (!resp.ok) {
      const errorText = await resp.text();
      throw new Error(`Backend error: ${resp.status} - ${errorText}`);
    }
    
    return NextResponse.json(await resp.json());
  } catch (error) {
    console.error("Providers API error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to fetch providers" },
      { status: 500 }
    );
  }
}

// POST - Add new provider
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    const resp = await fetch(`${BACKEND_URL}/api/v1/llm/providers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    
    if (!resp.ok) {
      const errorText = await resp.text();
      throw new Error(`Backend error: ${resp.status} - ${errorText}`);
    }
    
    return NextResponse.json(await resp.json());
  } catch (error) {
    console.error("Provider creation error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to create provider" },
      { status: 500 }
    );
  }
}
