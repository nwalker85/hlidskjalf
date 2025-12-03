# Production Environment
# =======================
# Full AWS deployment with high availability

terraform {
  required_version = ">= 1.6.0"

  # Production uses S3 backend (configured via CI/CD)
  # backend "s3" {
  #   bucket         = "ravenhelm-terraform-state"
  #   key            = "prod/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "ravenhelm-terraform-locks"
  # }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = local.tags
  }
}

variable "environment" {
  default = "prod"
}

variable "app_version" {
  description = "Application version to deploy"
  type        = string
}

variable "region" {
  default = "us-east-1"
}

variable "domain" {
  default = "ravenhelm.co"  # Production domain
}

locals {
  app_name = "ravenhelm-app"
  
  tags = {
    Environment = var.environment
    Project     = local.app_name
    ManagedBy   = "terraform"
    CostCenter  = "platform"
  }

  # Production sizing
  app_config = {
    min_instances     = 2
    max_instances     = 10
    instance_type     = "t3.large"
    health_check_path = "/health"
    cpu               = 1024
    memory            = 2048
  }

  db_config = {
    instance_class    = "db.t3.medium"
    allocated_storage = 100
    multi_az          = true
    backup_retention  = 30
  }
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# VPC
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${local.app_name}-${var.environment}"
  cidr = "10.0.0.0/16"

  azs             = slice(data.aws_availability_zones.available.names, 0, 3)
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway     = true
  single_nat_gateway     = false  # HA NAT gateways
  one_nat_gateway_per_az = true

  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = local.tags
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${local.app_name}-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  configuration {
    execute_command_configuration {
      logging = "OVERRIDE"
      log_configuration {
        cloud_watch_log_group_name = aws_cloudwatch_log_group.ecs.name
      }
    }
  }

  tags = local.tags
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${local.app_name}-${var.environment}"
  retention_in_days = 30

  tags = local.tags
}

# ALB
resource "aws_lb" "main" {
  name               = "${local.app_name}-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets

  enable_deletion_protection = true

  tags = local.tags
}

# ALB Security Group
resource "aws_security_group" "alb" {
  name_prefix = "${local.app_name}-alb-"
  vpc_id      = module.vpc.vpc_id

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

  lifecycle {
    create_before_destroy = true
  }
}

# RDS PostgreSQL
resource "aws_db_instance" "main" {
  identifier = "${local.app_name}-${var.environment}"

  engine         = "postgres"
  engine_version = "16"
  instance_class = local.db_config.instance_class

  allocated_storage     = local.db_config.allocated_storage
  max_allocated_storage = local.db_config.allocated_storage * 2
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = "app_prod"
  username = "app_admin"
  password = random_password.db_password.result

  multi_az                = local.db_config.multi_az
  db_subnet_group_name    = aws_db_subnet_group.main.name
  vpc_security_group_ids  = [aws_security_group.db.id]

  backup_retention_period = local.db_config.backup_retention
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  deletion_protection = true
  skip_final_snapshot = false
  final_snapshot_identifier = "${local.app_name}-${var.environment}-final"

  performance_insights_enabled = true

  tags = local.tags
}

resource "random_password" "db_password" {
  length  = 32
  special = false
}

resource "aws_db_subnet_group" "main" {
  name       = "${local.app_name}-${var.environment}"
  subnet_ids = module.vpc.private_subnets

  tags = local.tags
}

resource "aws_security_group" "db" {
  name_prefix = "${local.app_name}-db-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  tags = local.tags
}

# App Security Group
resource "aws_security_group" "app" {
  name_prefix = "${local.app_name}-app-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

# Store DB password in Secrets Manager
resource "aws_secretsmanager_secret" "db_password" {
  name = "${local.app_name}/${var.environment}/db-password"

  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = random_password.db_password.result
}

# Outputs
output "vpc_id" {
  value = module.vpc.vpc_id
}

output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "db_endpoint" {
  value     = aws_db_instance.main.endpoint
  sensitive = true
}

output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "app_url" {
  value = "https://${local.app_name}.${var.domain}"
}

