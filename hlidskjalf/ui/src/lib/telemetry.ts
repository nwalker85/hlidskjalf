/**
 * OpenTelemetry instrumentation for Hliðskjálf UI
 * 
 * Sends traces, metrics, and performance data to Grafana Alloy
 * for visualization in Grafana dashboards.
 */

import { WebTracerProvider } from '@opentelemetry/sdk-trace-web';
import { Resource } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-base';
import { registerInstrumentations } from '@opentelemetry/instrumentation';
import { FetchInstrumentation } from '@opentelemetry/instrumentation-fetch';
import { DocumentLoadInstrumentation } from '@opentelemetry/instrumentation-document-load';
import { MeterProvider, PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';

// Determine the OTLP endpoint based on environment
// Use the same protocol as the page to avoid mixed content errors
function getOTLPEndpoint(): string {
  if (typeof window === 'undefined') {
    return process.env.NEXT_PUBLIC_OTLP_ENDPOINT || 'https://otel.ravenhelm.test';
  }
  
  const hostname = window.location.hostname;
  const protocol = window.location.protocol; // 'http:' or 'https:'
  
  // Extract the base domain (ravenhelm.test, ravenhelm.dev, ravenhelm.ai)
  const domain = hostname.split('.').slice(-2).join('.');
  
  // Route through Traefik using the otel subdomain
  // This endpoint is configured in ravenhelm-proxy/dynamic.yml as otel-svc
  return `${protocol}//otel.${domain}`;
}

const OTLP_ENDPOINT = getOTLPEndpoint();

let isInitialized = false;

export function initTelemetry() {
  // Prevent double initialization
  if (isInitialized) {
    console.log('[Telemetry] Already initialized');
    return;
  }

  // Only initialize in browser
  if (typeof window === 'undefined') {
    return;
  }

  try {
    // Create resource with service information
    const resource = new Resource({
      [SemanticResourceAttributes.SERVICE_NAME]: 'hlidskjalf-ui',
      [SemanticResourceAttributes.SERVICE_VERSION]: '1.0.0',
      [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: process.env.NODE_ENV || 'development',
    });

    // =========================================================================
    // TRACES - Configure trace provider and exporter
    // =========================================================================
    const traceProvider = new WebTracerProvider({
      resource,
    });

    // Export traces to Grafana Alloy via OTLP HTTP
    const traceExporter = new OTLPTraceExporter({
      url: `${OTLP_ENDPOINT}/v1/traces`,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    traceProvider.addSpanProcessor(new BatchSpanProcessor(traceExporter, {
      maxQueueSize: 100,
      scheduledDelayMillis: 5000, // Export every 5 seconds
    }));

    traceProvider.register();

    // =========================================================================
    // METRICS - Configure metrics provider and exporter
    // =========================================================================
    const metricExporter = new OTLPMetricExporter({
      url: `${OTLP_ENDPOINT}/v1/metrics`,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    const metricReader = new PeriodicExportingMetricReader({
      exporter: metricExporter,
      exportIntervalMillis: 10000, // Export every 10 seconds
    });

    const meterProvider = new MeterProvider({
      resource,
      readers: [metricReader],
    });

    // =========================================================================
    // INSTRUMENTATION - Auto-instrument fetch and page load
    // =========================================================================
    registerInstrumentations({
      instrumentations: [
        // Instrument fetch API calls
        new FetchInstrumentation({
          propagateTraceHeaderCorsUrls: [
            /ravenhelm\.test/,
            /ravenhelm\.dev/,
            /ravenhelm\.ai/,
            /localhost/,
          ],
          clearTimingResources: true,
          applyCustomAttributesOnSpan: (span, request, result) => {
            // Add custom attributes to spans
            if (request instanceof Request) {
              const url = new URL(request.url);
              span.setAttribute('http.target', url.pathname);
              span.setAttribute('http.host', url.host);
            }
            if (result instanceof Response) {
              span.setAttribute('http.status_code', result.status);
            }
          },
        }),
        // Instrument document load events
        new DocumentLoadInstrumentation(),
      ],
    });

    isInitialized = true;
    console.log('[Telemetry] OpenTelemetry initialized successfully');
    console.log(`[Telemetry] Exporting to: ${OTLP_ENDPOINT}`);
  } catch (error) {
    console.error('[Telemetry] Failed to initialize OpenTelemetry:', error);
  }
}

/**
 * Get a tracer for manual instrumentation
 */
export function getTracer(name: string = 'hlidskjalf-ui') {
  const { trace } = require('@opentelemetry/api');
  return trace.getTracer(name);
}

/**
 * Get a meter for custom metrics
 */
export function getMeter(name: string = 'hlidskjalf-ui') {
  const { metrics } = require('@opentelemetry/api');
  return metrics.getMeter(name);
}

/**
 * Utility to wrap async functions with tracing
 */
export function withTrace<T>(
  operationName: string,
  fn: () => Promise<T>,
  attributes?: Record<string, string | number | boolean>
): Promise<T> {
  const tracer = getTracer();
  const { trace } = require('@opentelemetry/api');
  
  return tracer.startActiveSpan(operationName, async (span: any) => {
    if (attributes) {
      Object.entries(attributes).forEach(([key, value]) => {
        span.setAttribute(key, value);
      });
    }

    try {
      const result = await fn();
      span.setStatus({ code: 1 }); // OK
      return result;
    } catch (error) {
      span.setStatus({ 
        code: 2, // ERROR
        message: error instanceof Error ? error.message : 'Unknown error'
      });
      span.recordException(error as Error);
      throw error;
    } finally {
      span.end();
    }
  });
}

