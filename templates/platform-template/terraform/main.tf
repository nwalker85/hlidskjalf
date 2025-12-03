# Ravenhelm Platform - Main Terraform Configuration
# ==================================================
# This is the root module that orchestrates all platform infrastructure

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

# Variables
variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "ravenhelm-app"
}

variable "app_version" {
  description = "Application version/image tag"
  type        = string
  default     = "latest"
}

variable "domain" {
  description = "Base domain"
  type        = string
  default     = "ravenhelm.test"
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

# Locals
locals {
  common_tags = {
    Environment = var.environment
    Project     = var.app_name
    ManagedBy   = "terraform"
    GitCommit   = var.app_version
  }

  # Environment-specific settings
  env_config = {
    dev = {
      instance_count = 1
      instance_type  = "t3.small"
      enable_monitoring = false
      enable_backups    = false
    }
    staging = {
      instance_count = 2
      instance_type  = "t3.medium"
      enable_monitoring = true
      enable_backups    = false
    }
    prod = {
      instance_count = 3
      instance_type  = "t3.large"
      enable_monitoring = true
      enable_backups    = true
    }
  }

  config = local.env_config[var.environment]
}

# Outputs
output "environment" {
  value = var.environment
}

output "app_url" {
  value = "https://${var.environment}.${var.app_name}.${var.domain}"
}

output "config" {
  value = local.config
}

