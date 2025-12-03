/**
 * API client for Hliðskjálf
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://hlidskjalf-api.ravenhelm.test";

export interface PlatformOverview {
  total_projects: number;
  total_deployments: number;
  healthy_deployments: number;
  unhealthy_deployments: number;
  ports_allocated: number;
  ports_available: number;
  environments: Record<string, number>;
  recent_health_checks: HealthCheck[];
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  git_repo_url: string | null;
  subdomain: string;
  project_type: string;
  created_at: string;
  ports: PortAllocation[];
}

export interface PortAllocation {
  id: number;
  project_id: string;
  service_name: string;
  port: number;
  port_type: "http" | "https" | "grpc" | "metrics" | "database" | "custom";
  environment: string;
  internal_port: number | null;
  auto_assigned: boolean;
  description: string | null;
  created_at: string;
}

export interface Deployment {
  id: string;
  project_id: string;
  environment: string;
  status: "pending" | "deploying" | "running" | "stopped" | "failed" | "unhealthy";
  health_status: "healthy" | "degraded" | "unhealthy" | "unknown";
  version: string | null;
  git_commit: string | null;
  deployed_at: string;
  last_health_check: string | null;
}

export interface HealthCheck {
  deployment_id: string;
  status: "healthy" | "degraded" | "unhealthy" | "unknown";
  response_time_ms: number | null;
  metrics_snapshot: Record<string, any> | null;
  checked_at: string;
}

export interface NornsChatRequest {
  message: string;
  thread_id?: string;
}

export interface NornsChatResponse {
  response: string;
  thread_id: string;
  current_norn: "urd" | "verdandi" | "skuld";
}

class HlidskjalfAPI {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  // Platform Overview
  async getOverview(): Promise<PlatformOverview> {
    return this.request("/api/v1/overview");
  }

  // Projects
  async listProjects(): Promise<Project[]> {
    return this.request("/api/v1/projects");
  }

  async getProject(projectId: string): Promise<Project> {
    return this.request(`/api/v1/projects/${projectId}`);
  }

  async createProject(project: {
    id: string;
    name: string;
    subdomain: string;
    description?: string;
    git_repo_url?: string;
  }): Promise<Project> {
    return this.request("/api/v1/projects", {
      method: "POST",
      body: JSON.stringify(project),
    });
  }

  // Ports
  async listPorts(projectId?: string): Promise<PortAllocation[]> {
    const params = projectId ? `?project_id=${projectId}` : "";
    return this.request(`/api/v1/ports${params}`);
  }

  async getPortSummary(): Promise<Record<string, any>> {
    return this.request("/api/v1/ports/summary");
  }

  async allocatePort(request: {
    project_id: string;
    service_name: string;
    port_type?: string;
    environment?: string;
  }): Promise<PortAllocation> {
    return this.request("/api/v1/ports/allocate", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  // Deployments
  async listDeployments(filters?: {
    project_id?: string;
    environment?: string;
    status?: string;
  }): Promise<Deployment[]> {
    const params = new URLSearchParams();
    if (filters?.project_id) params.set("project_id", filters.project_id);
    if (filters?.environment) params.set("environment", filters.environment);
    if (filters?.status) params.set("status", filters.status);
    
    const query = params.toString() ? `?${params.toString()}` : "";
    return this.request(`/api/v1/deployments${query}`);
  }

  async triggerHealthCheck(deploymentId: string): Promise<HealthCheck> {
    return this.request(`/api/v1/deployments/${deploymentId}/health-check`, {
      method: "POST",
    });
  }

  // Nginx
  async getNginxConfig(): Promise<{ config: string }> {
    return this.request("/api/v1/nginx/config");
  }

  // The Norns
  async chatWithNorns(request: NornsChatRequest): Promise<NornsChatResponse> {
    return this.request("/api/v1/norns/chat", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async getNornWisdom(): Promise<{ wisdom: string; from: string }> {
    return this.request("/api/v1/norns/wisdom");
  }

  // Health
  async checkHealth(): Promise<{ status: string }> {
    return this.request("/health");
  }
}

export const api = new HlidskjalfAPI();
export default api;

