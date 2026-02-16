/**
 * Tools API Route
 * 
 * Proxies requests to Bifrost tool registry
 */

import { NextRequest, NextResponse } from "next/server";

const BIFROST_URL = process.env.BIFROST_URL || "http://bifrost-gateway:8080";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const category = searchParams.get("category");
  const source = searchParams.get("source");
  const enabled_only = searchParams.get("enabled_only");
  const tag = searchParams.get("tag");

  try {
    const params = new URLSearchParams();
    if (category) params.append("category", category);
    if (source) params.append("source", source);
    if (enabled_only) params.append("enabled_only", enabled_only);
    if (tag) params.append("tag", tag);

    const response = await fetch(`${BIFROST_URL}/api/tools?${params}`, {
      headers: {
        "Content-Type": "application/json",
      },
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`Bifrost returned ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Failed to fetch tools:", error);
    
    // Return mock data for development when Bifrost is not available
    return NextResponse.json({
      tools: getMockTools(),
      total: getMockTools().length,
      categories: getMockCategories(),
    });
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    const response = await fetch(`${BIFROST_URL}/api/tools/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const error = await response.json();
      return NextResponse.json(error, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Failed to register tool:", error);
    return NextResponse.json(
      { error: "Failed to register tool" },
      { status: 500 }
    );
  }
}

// Mock data for development
function getMockTools() {
  return [
    {
      name: "get_platform_overview",
      description: "Observe the current state of all Nine Realms",
      category: "platform",
      source: "norns",
      enabled: true,
      parameters: [],
      norn: "verdandi",
      tags: ["norn:verdandi", "category:platform"],
    },
    {
      name: "list_projects",
      description: "List all projects registered in the platform",
      category: "platform",
      source: "norns",
      enabled: true,
      parameters: [{ name: "realm", type: "string", required: false }],
      norn: "verdandi",
      tags: ["norn:verdandi", "category:platform"],
    },
    {
      name: "check_deployment_health",
      description: "Check the health of a specific deployment",
      category: "platform",
      source: "norns",
      enabled: true,
      parameters: [{ name: "deployment_id", type: "string", required: true }],
      norn: "verdandi",
      tags: ["norn:verdandi", "category:platform"],
    },
    {
      name: "analyze_logs",
      description: "Analyze logs from the past",
      category: "history",
      source: "norns",
      enabled: true,
      parameters: [
        { name: "project_id", type: "string", required: true },
        { name: "time_range", type: "string", required: false },
      ],
      norn: "urd",
      tags: ["norn:urd", "category:history"],
    },
    {
      name: "get_health_trends",
      description: "Analyze health check history",
      category: "history",
      source: "norns",
      enabled: true,
      parameters: [{ name: "deployment_id", type: "string", required: true }],
      norn: "urd",
      tags: ["norn:urd", "category:history"],
    },
    {
      name: "allocate_ports",
      description: "Weave new port allocations for services",
      category: "planning",
      source: "norns",
      enabled: true,
      parameters: [
        { name: "project_id", type: "string", required: true },
        { name: "services", type: "array", required: true },
      ],
      norn: "skuld",
      tags: ["norn:skuld", "category:planning"],
    },
    {
      name: "predict_issues",
      description: "Peer into fate to predict potential issues",
      category: "planning",
      source: "norns",
      enabled: true,
      parameters: [{ name: "project_id", type: "string", required: false }],
      norn: "skuld",
      tags: ["norn:skuld", "category:planning"],
    },
    {
      name: "muninn_recall",
      description: "Recall memories from long-term storage",
      category: "memory",
      source: "norns",
      enabled: true,
      parameters: [{ name: "query", type: "string", required: true }],
      tags: ["category:memory"],
    },
    {
      name: "skills_retrieve",
      description: "Retrieve relevant skills using RAG",
      category: "skills",
      source: "norns",
      enabled: true,
      parameters: [{ name: "query", type: "string", required: true }],
      tags: ["category:skills"],
    },
    {
      name: "workspace_read",
      description: "Read a file from the workspace",
      category: "workspace",
      source: "norns",
      enabled: true,
      parameters: [{ name: "path", type: "string", required: true }],
      tags: ["category:workspace"],
    },
  ];
}

function getMockCategories() {
  return {
    platform: 3,
    history: 2,
    planning: 2,
    memory: 1,
    skills: 1,
    workspace: 1,
  };
}

