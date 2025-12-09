import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.BACKEND_URL ||
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://hlidskjalf:8900";

// GET - Get models for a provider
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const resp = await fetch(`${BACKEND_URL}/api/v1/llm/providers/${params.id}/models`, {
      cache: "no-store",
    });
    
    if (!resp.ok) {
      throw new Error(`Backend error: ${resp.status}`);
    }
    
    return NextResponse.json(await resp.json());
  } catch (error) {
    console.error("Provider models fetch error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to fetch models" },
      { status: 500 }
    );
  }
}

// POST - Add model to provider
export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const body = await request.json();
    
    const resp = await fetch(`${BACKEND_URL}/api/v1/llm/providers/${params.id}/models`, {
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
    console.error("Model creation error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to add model" },
      { status: 500 }
    );
  }
}

