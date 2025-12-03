# Staging Environment
# ====================
# Uses LocalStack for AWS simulation in local development
# Switch to real AWS for remote staging

terraform {
  required_version = ">= 1.6.0"
}

provider "aws" {
  region = var.region

  # LocalStack configuration for local testing
  skip_credentials_validation = var.use_localstack
  skip_metadata_api_check     = var.use_localstack
  skip_requesting_account_id  = var.use_localstack

  endpoints {
    ec2            = var.use_localstack ? "http://localhost:4566" : null
    ecs            = var.use_localstack ? "http://localhost:4566" : null
    iam            = var.use_localstack ? "http://localhost:4566" : null
    s3             = var.use_localstack ? "http://localhost:4566" : null
    secretsmanager = var.use_localstack ? "http://localhost:4566" : null
    ssm            = var.use_localstack ? "http://localhost:4566" : null
    rds            = var.use_localstack ? "http://localhost:4566" : null
  }
}

variable "environment" {
  default = "staging"
}

variable "app_version" {
  default = "latest"
}

variable "region" {
  default = "us-east-1"
}

variable "use_localstack" {
  default = true
}

locals {
  app_name = "ravenhelm-app"
  domain   = "ravenhelm.test"
  
  tags = {
    Environment = var.environment
    Project     = local.app_name
    ManagedBy   = "terraform"
  }
}

# VPC (simulated in LocalStack)
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.tags, {
    Name = "${local.app_name}-${var.environment}-vpc"
  })
}

# Subnets
resource "aws_subnet" "public" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index + 1}.0/24"
  availability_zone = "${var.region}${count.index == 0 ? "a" : "b"}"

  tags = merge(local.tags, {
    Name = "${local.app_name}-${var.environment}-public-${count.index + 1}"
  })
}

# Security Group
resource "aws_security_group" "app" {
  name_prefix = "${local.app_name}-${var.environment}-"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

# ECS Cluster (for container deployment)
resource "aws_ecs_cluster" "main" {
  name = "${local.app_name}-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = local.tags
}

# Parameter Store for secrets
resource "aws_ssm_parameter" "database_url" {
  name  = "/${local.app_name}/${var.environment}/database_url"
  type  = "SecureString"
  value = "postgresql://staging:staging@rds-endpoint:5432/app_staging"

  tags = local.tags
}

# S3 Bucket for artifacts
resource "aws_s3_bucket" "artifacts" {
  bucket = "${local.app_name}-${var.environment}-artifacts"

  tags = local.tags
}

output "vpc_id" {
  value = aws_vpc.main.id
}

output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "app_url" {
  value = "https://staging.${local.app_name}.${local.domain}"
}

