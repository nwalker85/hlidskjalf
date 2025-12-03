###############################################################################
# Ravenmaskos Infrastructure - Main Configuration
###############################################################################

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
  }

  # Backend configuration - uncomment and configure for remote state
  # backend "s3" {
  #   bucket         = "ravenmaskos-terraform-state"
  #   key            = "infrastructure/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "ravenmaskos-terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "ravenmaskos"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

###############################################################################
# VPC Module
###############################################################################

module "vpc" {
  source = "./modules/vpc"

  name        = "${var.project_name}-${var.environment}"
  environment = var.environment

  cidr_block           = var.vpc_cidr
  availability_zones   = slice(data.aws_availability_zones.available.names, 0, 3)
  private_subnet_cidrs = var.private_subnet_cidrs
  public_subnet_cidrs  = var.public_subnet_cidrs

  enable_nat_gateway = true
  single_nat_gateway = var.environment != "production"

  tags = var.tags
}

###############################################################################
# EKS Module
###############################################################################

module "eks" {
  source = "./modules/eks"

  cluster_name    = "${var.project_name}-${var.environment}"
  cluster_version = var.eks_cluster_version
  environment     = var.environment

  vpc_id          = module.vpc.vpc_id
  private_subnets = module.vpc.private_subnet_ids

  # Node group configuration
  node_groups = {
    general = {
      instance_types = var.eks_node_instance_types
      min_size       = var.environment == "production" ? 3 : 1
      max_size       = var.environment == "production" ? 10 : 5
      desired_size   = var.environment == "production" ? 3 : 2
    }
  }

  # Enable IRSA for service accounts
  enable_irsa = true

  tags = var.tags
}

###############################################################################
# RDS Module (PostgreSQL)
###############################################################################

module "rds" {
  source = "./modules/rds"

  identifier     = "${var.project_name}-${var.environment}"
  engine_version = "15.4"
  environment    = var.environment

  vpc_id             = module.vpc.vpc_id
  subnet_ids         = module.vpc.private_subnet_ids
  security_group_ids = [module.eks.node_security_group_id]

  instance_class    = var.rds_instance_class
  allocated_storage = var.rds_allocated_storage
  multi_az          = var.environment == "production"

  database_name   = "ravenmaskos"
  master_username = "ravenmaskos_admin"
  # Password managed via Secrets Manager

  # Enable encryption
  storage_encrypted = true

  # Backup configuration
  backup_retention_period = var.environment == "production" ? 30 : 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  # Performance Insights
  performance_insights_enabled = var.environment == "production"

  tags = var.tags
}

###############################################################################
# ElastiCache Module (Redis)
###############################################################################

module "elasticache" {
  source = "./modules/elasticache"

  cluster_id   = "${var.project_name}-${var.environment}"
  environment  = var.environment

  vpc_id             = module.vpc.vpc_id
  subnet_ids         = module.vpc.private_subnet_ids
  security_group_ids = [module.eks.node_security_group_id]

  node_type       = var.redis_node_type
  num_cache_nodes = var.environment == "production" ? 2 : 1

  # Enable encryption in transit
  transit_encryption_enabled = true
  at_rest_encryption_enabled = true

  # Auth token managed via Secrets Manager
  auth_token_enabled = true

  tags = var.tags
}

###############################################################################
# MSK Module (Kafka)
###############################################################################

module "msk" {
  source = "./modules/msk"

  cluster_name = "${var.project_name}-${var.environment}"
  environment  = var.environment

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids

  kafka_version = "3.5.1"
  broker_count  = var.environment == "production" ? 3 : 2

  broker_instance_type = var.msk_broker_instance_type
  broker_volume_size   = var.msk_broker_volume_size

  # Security
  encryption_in_transit = "TLS"
  encryption_at_rest    = true

  # SASL/SCRAM authentication
  sasl_scram_enabled = true

  tags = var.tags
}

###############################################################################
# Outputs
###############################################################################

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "eks_cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = module.rds.endpoint
}

output "elasticache_endpoint" {
  description = "ElastiCache endpoint"
  value       = module.elasticache.endpoint
}

output "msk_bootstrap_brokers" {
  description = "MSK bootstrap brokers"
  value       = module.msk.bootstrap_brokers_tls
}
