import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.BACKEND_URL ||
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://hlidskjalf:8900";

// PUT - Update configuration for specific interaction type
export async function PUT(
  request: NextRequest,
  { params }: { params: { interaction_type: string } }
) {
  try {
    const { interaction_type } = params;
    const body = await request.json();
    
    const resp = await fetch(`${BACKEND_URL}/api/v1/llm/config/${interaction_type}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    
    if (!resp.ok) {
      const errorText = await resp.text();
      throw new Error(`Backend error: ${resp.status} - ${errorText}`);
    }
    
    return NextResponse.json(await resp.json());
  } catch (error) {
    console.error("LLM config update error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to update config" },
      { status: 500 }
    );
  }
}

