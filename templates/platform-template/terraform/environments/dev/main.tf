# Development Environment
# ========================

terraform {
  required_version = ">= 1.6.0"
}

# For local development, use Docker provider
provider "docker" {
  host = "unix:///var/run/docker.sock"
}

variable "app_version" {
  default = "latest"
}

variable "environment" {
  default = "dev"
}

locals {
  app_name = "ravenhelm-app"
  domain   = "ravenhelm.test"
  
  labels = {
    "traefik.enable" = "true"
    "traefik.http.routers.${local.app_name}-dev.rule" = "Host(`dev.${local.app_name}.${local.domain}`)"
    "traefik.http.routers.${local.app_name}-dev.tls"  = "true"
    "environment" = var.environment
    "managed-by"  = "terraform"
  }
}

# Docker Network (connect to existing ravenhelm network)
data "docker_network" "ravenhelm" {
  name = "ravenhelm-network"
}

# Application Container
resource "docker_container" "app" {
  name  = "${local.app_name}-${var.environment}"
  image = "registry.gitlab.ravenhelm.test/ravenhelm/${local.app_name}:${var.app_version}"

  restart = "unless-stopped"

  networks_advanced {
    name = data.docker_network.ravenhelm.name
  }

  env = [
    "ENVIRONMENT=${var.environment}",
    "LOG_LEVEL=debug",
    "DATABASE_URL=postgresql://postgres:5432/app_dev",
    "REDIS_URL=redis://redis:6379/0",
    "NATS_URL=nats://nats:4222",
  ]

  dynamic "labels" {
    for_each = local.labels
    content {
      label = labels.key
      value = labels.value
    }
  }

  healthcheck {
    test         = ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval     = "30s"
    timeout      = "10s"
    retries      = 3
    start_period = "30s"
  }
}

# Database (dev uses shared postgres)
# In dev, we just create a database in the shared postgres instance

output "app_container_id" {
  value = docker_container.app.id
}

output "app_url" {
  value = "https://dev.${local.app_name}.${local.domain}"
}

