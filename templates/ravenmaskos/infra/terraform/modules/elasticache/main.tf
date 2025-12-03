###############################################################################
# ElastiCache Redis Module
###############################################################################

variable "cluster_id" {
  description = "ElastiCache cluster ID"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs"
  type        = list(string)
}

variable "security_group_ids" {
  description = "Security group IDs allowed to connect"
  type        = list(string)
}

variable "node_type" {
  description = "ElastiCache node type"
  type        = string
}

variable "num_cache_nodes" {
  description = "Number of cache nodes"
  type        = number
  default     = 1
}

variable "transit_encryption_enabled" {
  description = "Enable encryption in transit"
  type        = bool
  default     = true
}

variable "at_rest_encryption_enabled" {
  description = "Enable encryption at rest"
  type        = bool
  default     = true
}

variable "auth_token_enabled" {
  description = "Enable AUTH token"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags for resources"
  type        = map(string)
  default     = {}
}

###############################################################################
# Subnet Group
###############################################################################

resource "aws_elasticache_subnet_group" "main" {
  name       = var.cluster_id
  subnet_ids = var.subnet_ids

  tags = var.tags
}

###############################################################################
# Security Group
###############################################################################

resource "aws_security_group" "redis" {
  name        = "${var.cluster_id}-redis-sg"
  description = "Security group for ElastiCache Redis"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Redis from allowed security groups"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = var.security_group_ids
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.cluster_id}-redis-sg"
  })
}

###############################################################################
# Auth Token in Secrets Manager
###############################################################################

resource "random_password" "auth_token" {
  count   = var.auth_token_enabled ? 1 : 0
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "redis" {
  count = var.auth_token_enabled ? 1 : 0
  name  = "${var.environment}/${var.cluster_id}/redis"

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "redis" {
  count     = var.auth_token_enabled ? 1 : 0
  secret_id = aws_secretsmanager_secret.redis[0].id
  secret_string = jsonencode({
    auth_token = random_password.auth_token[0].result
    url        = "rediss://:${random_password.auth_token[0].result}@${aws_elasticache_replication_group.main.primary_endpoint_address}:6379/0"
  })
}

###############################################################################
# ElastiCache Replication Group
###############################################################################

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = var.cluster_id
  description          = "Redis cluster for ${var.cluster_id}"

  node_type            = var.node_type
  num_cache_clusters   = var.num_cache_nodes
  parameter_group_name = "default.redis7"
  engine_version       = "7.0"
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]

  transit_encryption_enabled = var.transit_encryption_enabled
  at_rest_encryption_enabled = var.at_rest_encryption_enabled
  auth_token                 = var.auth_token_enabled ? random_password.auth_token[0].result : null

  automatic_failover_enabled = var.num_cache_nodes > 1
  multi_az_enabled           = var.num_cache_nodes > 1

  snapshot_retention_limit = var.environment == "production" ? 7 : 0
  snapshot_window          = "03:00-05:00"
  maintenance_window       = "mon:05:00-mon:07:00"

  tags = var.tags
}

###############################################################################
# Outputs
###############################################################################

output "endpoint" {
  description = "Redis primary endpoint"
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "port" {
  description = "Redis port"
  value       = aws_elasticache_replication_group.main.port
}

output "secret_arn" {
  description = "Secrets Manager secret ARN"
  value       = var.auth_token_enabled ? aws_secretsmanager_secret.redis[0].arn : null
}
