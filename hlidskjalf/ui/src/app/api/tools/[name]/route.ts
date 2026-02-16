/**
 * Single Tool API Route
 * 
 * Handles enable/disable and deletion of tools
 */

import { NextRequest, NextResponse } from "next/server";

const BIFROST_URL = process.env.BIFROST_URL || "http://bifrost-gateway:8080";

export async function GET(
  request: NextRequest,
  { params }: { params: { name: string } }
) {
  const { name } = params;

  try {
    const response = await fetch(`${BIFROST_URL}/api/tools/${name}`, {
      headers: {
        "Content-Type": "application/json",
      },
      cache: "no-store",
    });

    if (!response.ok) {
      if (response.status === 404) {
        return NextResponse.json(
          { error: `Tool '${name}' not found` },
          { status: 404 }
        );
      }
      throw new Error(`Bifrost returned ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Failed to fetch tool:", error);
    return NextResponse.json(
      { error: "Failed to fetch tool details" },
      { status: 500 }
    );
  }
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: { name: string } }
) {
  const { name } = params;

  try {
    const body = await request.json();
    const { enabled } = body;

    const endpoint = enabled
      ? `${BIFROST_URL}/api/tools/${name}/enable`
      : `${BIFROST_URL}/api/tools/${name}/disable`;

    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      if (response.status === 404) {
        return NextResponse.json(
          { error: `Tool '${name}' not found` },
          { status: 404 }
        );
      }
      throw new Error(`Bifrost returned ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Failed to update tool:", error);
    return NextResponse.json(
      { error: "Failed to update tool" },
      { status: 500 }
    );
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { name: string } }
) {
  const { name } = params;

  try {
    const response = await fetch(`${BIFROST_URL}/api/tools/${name}`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      const error = await response.json();
      return NextResponse.json(error, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Failed to delete tool:", error);
    return NextResponse.json(
      { error: "Failed to delete tool" },
      { status: 500 }
    );
  }
}

