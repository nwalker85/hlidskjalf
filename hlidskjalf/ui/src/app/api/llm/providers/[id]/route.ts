import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.BACKEND_URL ||
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://hlidskjalf:8900";

// PUT - Update provider
export async function PUT(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const body = await request.json();
    
    const resp = await fetch(`${BACKEND_URL}/api/v1/llm/providers/${params.id}`, {
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
    console.error("Provider update error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to update provider" },
      { status: 500 }
    );
  }
}

// DELETE - Remove provider
export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const resp = await fetch(`${BACKEND_URL}/api/v1/llm/providers/${params.id}`, {
      method: "DELETE",
    });
    
    if (!resp.ok) {
      const errorText = await resp.text();
      throw new Error(`Backend error: ${resp.status} - ${errorText}`);
    }
    
    return NextResponse.json(await resp.json());
  } catch (error) {
    console.error("Provider deletion error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to delete provider" },
      { status: 500 }
    );
  }
}

