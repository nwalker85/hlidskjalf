import { initApiPassthrough } from "langgraph-nextjs-api-passthrough";

// LANGGRAPH_API_URL defaults to ravenhelm.test domain (reverse proxy handles routing)
const apiUrl = process.env.LANGGRAPH_API_URL || "https://norns.ravenhelm.test";

export const { GET, POST, PUT, PATCH, DELETE, OPTIONS, runtime } =
  initApiPassthrough({
    apiUrl,
    apiKey: process.env.LANGSMITH_API_KEY,
    runtime: "edge",
  });

