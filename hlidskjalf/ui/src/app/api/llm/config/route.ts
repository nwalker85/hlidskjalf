import { NextRequest, NextResponse } from "next/server";

// Resolve the control-plane API base URL in priority order:
// 1. BACKEND_URL (explicit override)
// 2. INTERNAL_API_URL (if set by deployments)
// 3. NEXT_PUBLIC_API_URL (falls back to public domain w/ auth)
// 4. Default internal service address inside Docker
const BACKEND_URL =
  process.env.BACKEND_URL ||
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://hlidskjalf:8900";

interface LLMModelConfig {
  provider: string;
  model: string;
  temperature: number;
}

interface LLMConfiguration {
  reasoning: LLMModelConfig;
  tools: LLMModelConfig;
  subagents: LLMModelConfig;
}

interface ProviderInfo {
  id: string;
  name: string;
  available: boolean;
  models: string[];
  default_model: string;
}

// GET - Fetch current config or providers list
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const sessionId = searchParams.get("sessionId");
  
  try {
    if (sessionId) {
      // Get config for specific session
      const resp = await fetch(`${BACKEND_URL}/api/v1/llm/config/${sessionId}`, {
        cache: "no-store",
      });
      
      if (!resp.ok) {
        // Return defaults if session not found
        if (resp.status === 404) {
          return NextResponse.json({
            session_id: sessionId,
            reasoning: { provider: "ollama", model: "mistral-nemo:latest", temperature: 0.7 },
            tools: { provider: "ollama", model: "mistral-nemo:latest", temperature: 0.1 },
            subagents: { provider: "ollama", model: "mistral-nemo:latest", temperature: 0.5 },
          });
        }
        throw new Error(`Backend error: ${resp.status}`);
      }
      
      return NextResponse.json(await resp.json());
    } else {
      // Get available providers
      const resp = await fetch(`${BACKEND_URL}/api/v1/llm/providers`, {
        cache: "no-store",
      });
      
      if (!resp.ok) {
        throw new Error(`Backend error: ${resp.status}`);
      }
      
      return NextResponse.json(await resp.json());
    }
  } catch (error) {
    console.error("LLM config API error:", error);
    
    // Return fallback data on error
    if (sessionId) {
      return NextResponse.json({
        session_id: sessionId,
        reasoning: { provider: "ollama", model: "mistral-nemo:latest", temperature: 0.7 },
        tools: { provider: "ollama", model: "mistral-nemo:latest", temperature: 0.1 },
        subagents: { provider: "ollama", model: "mistral-nemo:latest", temperature: 0.5 },
      });
    }
    
    return NextResponse.json({
      providers: [
        {
          id: "ollama",
          name: "Ollama",
          available: true,
          models: ["mistral-nemo:latest", "llama3.1:8b"],
          default_model: "mistral-nemo:latest",
        },
        {
          id: "lmstudio",
          name: "LM Studio",
          available: true,
          models: ["local-model"],
          default_model: "local-model",
        },
        {
          id: "openai",
          name: "OpenAI",
          available: false,
          models: ["gpt-4o", "gpt-4o-mini"],
          default_model: "gpt-4o",
        },
      ],
    });
  }
}

// POST - Update config for a session
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { sessionId, config } = body;
    
    if (!sessionId) {
      return NextResponse.json(
        { error: "sessionId is required" },
        { status: 400 }
      );
    }
    
    const resp = await fetch(`${BACKEND_URL}/api/v1/llm/config/${sessionId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    
    if (!resp.ok) {
      const errorText = await resp.text();
      throw new Error(`Backend error: ${resp.status} - ${errorText}`);
    }
    
    return NextResponse.json(await resp.json());
  } catch (error) {
    console.error("LLM config POST error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to update config" },
      { status: 500 }
    );
  }
}
