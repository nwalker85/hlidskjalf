"use client";

import { useEffect } from "react";
import { initTelemetry } from "@/lib/telemetry";

/**
 * Client-side component to initialize OpenTelemetry
 * Must be a separate component to use "use client" directive
 */
export function TelemetryInitializer() {
  useEffect(() => {
    // Initialize telemetry on mount
    initTelemetry();
  }, []);

  return null; // This component doesn't render anything
}

