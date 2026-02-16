import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.BACKEND_URL ||
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://hlidskjalf:8900";

// GET - Get global configuration
export async function GET(request: NextRequest) {
  try {
    const resp = await fetch(`${BACKEND_URL}/api/v1/llm/config`, {
      cache: "no-store",
    });
    
    if (!resp.ok) {
      throw new Error(`Backend error: ${resp.status}`);
    }
    
    return NextResponse.json(await resp.json());
  } catch (error) {
    console.error("LLM config API error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to fetch config" },
      { status: 500 }
    );
  }
}
