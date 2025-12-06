import { NextRequest } from "next/server";

export async function GET(request: NextRequest) {
  const apiUrl =
    process.env.NEXT_PUBLIC_API_URL || "https://hlidskjalf-api.ravenhelm.test";

  try {
    const response = await fetch(`${apiUrl}/api/v1/llm/config/events`, {
      headers: {
        Accept: "text/event-stream",
      },
    });

    if (!response.ok || !response.body) {
      throw new Error("Failed to connect to llm config stream");
    }

    return new Response(response.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  } catch (error) {
    console.error("LLM config stream error:", error);
    return new Response(
      `data: ${JSON.stringify({
        type: "error",
        message: "Stream unavailable",
      })}\n\n`,
      {
        headers: {
          "Content-Type": "text/event-stream",
        },
      },
    );
  }
}

export const runtime = "edge";


