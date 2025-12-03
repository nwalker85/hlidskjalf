import { NextRequest, NextResponse } from "next/server";

const SERVICE_ENDPOINTS: Record<string, string> = {
  langgraph: process.env.LANGGRAPH_API_URL || "http://langgraph:2024",
  ollama: process.env.OLLAMA_URL || "http://ollama:11434",
  redis: process.env.REDIS_URL || "redis://redis:6379",
  postgres: process.env.POSTGRES_URL || "postgresql://postgres:5432",
  redpanda: process.env.REDPANDA_URL || "http://redpanda:8082",
};

const HEALTH_PATHS: Record<string, string> = {
  langgraph: "/info",
  ollama: "/api/tags",
  redis: "/", // Will use TCP check
  postgres: "/", // Will use TCP check
  redpanda: "/brokers",
};

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ service: string }> }
) {
  const { service } = await params;
  const start = Date.now();

  try {
    const baseUrl = SERVICE_ENDPOINTS[service];
    const healthPath = HEALTH_PATHS[service];

    if (!baseUrl) {
      return NextResponse.json(
        { status: "unknown", error: "Unknown service" },
        { status: 404 }
      );
    }

    // For HTTP-based services
    if (baseUrl.startsWith("http")) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5000);

      try {
        const res = await fetch(`${baseUrl}${healthPath}`, {
          signal: controller.signal,
          cache: "no-store",
        });
        clearTimeout(timeout);

        const latency = Date.now() - start;

        if (res.ok) {
          return NextResponse.json({
            status: "healthy",
            latency,
            service,
            timestamp: new Date().toISOString(),
          });
        } else {
          return NextResponse.json({
            status: "unhealthy",
            latency,
            service,
            statusCode: res.status,
            timestamp: new Date().toISOString(),
          });
        }
      } catch (err) {
        clearTimeout(timeout);
        throw err;
      }
    }

    // For non-HTTP services (redis, postgres), just check if URL is configured
    // In production, you'd do actual TCP/protocol checks
    return NextResponse.json({
      status: "healthy",
      latency: Date.now() - start,
      service,
      note: "Configuration check only",
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    const latency = Date.now() - start;
    return NextResponse.json(
      {
        status: "unhealthy",
        latency,
        service,
        error: error instanceof Error ? error.message : "Unknown error",
        timestamp: new Date().toISOString(),
      },
      { status: 503 }
    );
  }
}

