###############################################################################
# Amazon MSK (Kafka) Module
###############################################################################

variable "cluster_name" {
  description = "MSK cluster name"
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

variable "kafka_version" {
  description = "Kafka version"
  type        = string
  default     = "3.5.1"
}

variable "broker_count" {
  description = "Number of broker nodes"
  type        = number
  default     = 3
}

variable "broker_instance_type" {
  description = "Broker instance type"
  type        = string
  default     = "kafka.t3.small"
}

variable "broker_volume_size" {
  description = "Broker EBS volume size in GB"
  type        = number
  default     = 100
}

variable "encryption_in_transit" {
  description = "Encryption in transit (TLS, TLS_PLAINTEXT, PLAINTEXT)"
  type        = string
  default     = "TLS"
}

variable "encryption_at_rest" {
  description = "Enable encryption at rest"
  type        = bool
  default     = true
}

variable "sasl_scram_enabled" {
  description = "Enable SASL/SCRAM authentication"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags for resources"
  type        = map(string)
  default     = {}
}

###############################################################################
# Security Group
###############################################################################

resource "aws_security_group" "msk" {
  name        = "${var.cluster_name}-msk-sg"
  description = "Security group for MSK"
  vpc_id      = var.vpc_id

  ingress {
    description = "Kafka TLS from VPC"
    from_port   = 9094
    to_port     = 9094
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.main.cidr_block]
  }

  ingress {
    description = "Kafka SASL/SCRAM from VPC"
    from_port   = 9096
    to_port     = 9096
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.main.cidr_block]
  }

  ingress {
    description = "Zookeeper from VPC"
    from_port   = 2181
    to_port     = 2181
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.main.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-msk-sg"
  })
}

data "aws_vpc" "main" {
  id = var.vpc_id
}

###############################################################################
# KMS Key for Encryption
###############################################################################

resource "aws_kms_key" "msk" {
  count       = var.encryption_at_rest ? 1 : 0
  description = "KMS key for MSK ${var.cluster_name}"

  tags = var.tags
}

###############################################################################
# Secrets Manager for SASL/SCRAM
###############################################################################

resource "random_password" "kafka" {
  count   = var.sasl_scram_enabled ? 1 : 0
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "kafka" {
  count      = var.sasl_scram_enabled ? 1 : 0
  name       = "AmazonMSK_${var.cluster_name}_credentials"
  kms_key_id = var.encryption_at_rest ? aws_kms_key.msk[0].key_id : null

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "kafka" {
  count     = var.sasl_scram_enabled ? 1 : 0
  secret_id = aws_secretsmanager_secret.kafka[0].id
  secret_string = jsonencode({
    username = "ravenmaskos"
    password = random_password.kafka[0].result
  })
}

###############################################################################
# MSK Configuration
###############################################################################

resource "aws_msk_configuration" "main" {
  name = var.cluster_name

  kafka_versions = [var.kafka_version]

  server_properties = <<PROPERTIES
auto.create.topics.enable=false
default.replication.factor=3
min.insync.replicas=2
num.io.threads=8
num.network.threads=5
num.partitions=1
num.replica.fetchers=2
socket.receive.buffer.bytes=102400
socket.request.max.bytes=104857600
socket.send.buffer.bytes=102400
unclean.leader.election.enable=false
PROPERTIES
}

###############################################################################
# MSK Cluster
###############################################################################

resource "aws_msk_cluster" "main" {
  cluster_name           = var.cluster_name
  kafka_version          = var.kafka_version
  number_of_broker_nodes = var.broker_count

  broker_node_group_info {
    instance_type   = var.broker_instance_type
    client_subnets  = var.subnet_ids
    security_groups = [aws_security_group.msk.id]

    storage_info {
      ebs_storage_info {
        volume_size = var.broker_volume_size
      }
    }
  }

  configuration_info {
    arn      = aws_msk_configuration.main.arn
    revision = aws_msk_configuration.main.latest_revision
  }

  encryption_info {
    encryption_at_rest_kms_key_arn = var.encryption_at_rest ? aws_kms_key.msk[0].arn : null

    encryption_in_transit {
      client_broker = var.encryption_in_transit
      in_cluster    = true
    }
  }

  dynamic "client_authentication" {
    for_each = var.sasl_scram_enabled ? [1] : []
    content {
      sasl {
        scram = true
      }
    }
  }

  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.msk.name
      }
    }
  }

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "msk" {
  name              = "/aws/msk/${var.cluster_name}"
  retention_in_days = var.environment == "production" ? 30 : 7

  tags = var.tags
}

###############################################################################
# Associate SCRAM Secret
###############################################################################

resource "aws_msk_scram_secret_association" "main" {
  count = var.sasl_scram_enabled ? 1 : 0

  cluster_arn     = aws_msk_cluster.main.arn
  secret_arn_list = [aws_secretsmanager_secret.kafka[0].arn]
}

###############################################################################
# Outputs
###############################################################################

output "cluster_arn" {
  description = "MSK cluster ARN"
  value       = aws_msk_cluster.main.arn
}

output "bootstrap_brokers_tls" {
  description = "TLS connection string"
  value       = aws_msk_cluster.main.bootstrap_brokers_tls
}

output "bootstrap_brokers_sasl_scram" {
  description = "SASL/SCRAM connection string"
  value       = var.sasl_scram_enabled ? aws_msk_cluster.main.bootstrap_brokers_sasl_scram : null
}

output "zookeeper_connect" {
  description = "Zookeeper connection string"
  value       = aws_msk_cluster.main.zookeeper_connect_string
}

output "secret_arn" {
  description = "Secrets Manager secret ARN for SASL credentials"
  value       = var.sasl_scram_enabled ? aws_secretsmanager_secret.kafka[0].arn : null
}
