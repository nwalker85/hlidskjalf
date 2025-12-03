#!/bin/bash
#
# Ravenhelm Database Backup to S3
# ================================
# Backs up PostgreSQL databases to LocalStack S3 (dev) or AWS S3 (prod)
#
# Usage:
#   ./scripts/backup-to-s3.sh                    # Backup all databases
#   ./scripts/backup-to-s3.sh hlidskjalf         # Backup specific database
#   ./scripts/backup-to-s3.sh --restore latest   # Restore latest backup
#
# Environment Variables:
#   AWS_ENDPOINT_URL  - LocalStack endpoint (default: http://localhost:4566)
#   POSTGRES_HOST     - PostgreSQL host (default: localhost)
#   POSTGRES_PORT     - PostgreSQL port (default: 5432)
#   POSTGRES_USER     - PostgreSQL user (default: postgres)
#   PGPASSWORD        - PostgreSQL password (set via env)
#   S3_BUCKET         - Target S3 bucket (default: ravenhelm-backups)
#

set -e

# =========================================================================
# Configuration
# =========================================================================

# LocalStack endpoint (use empty for real AWS)
AWS_ENDPOINT_URL="${AWS_ENDPOINT_URL:-http://localhost:4566}"
AWS_REGION="${AWS_REGION:-us-east-1}"

# PostgreSQL settings
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"

# S3 bucket
S3_BUCKET="${S3_BUCKET:-ravenhelm-backups}"

# Backup settings
BACKUP_RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
DATE_PREFIX=$(date +%Y/%m/%d)

# =========================================================================
# Helper Functions
# =========================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    log "ERROR: $1" >&2
    exit 1
}

# AWS CLI wrapper that handles LocalStack
aws_cmd() {
    if [ -n "$AWS_ENDPOINT_URL" ]; then
        aws --endpoint-url "$AWS_ENDPOINT_URL" --region "$AWS_REGION" "$@"
    else
        aws --region "$AWS_REGION" "$@"
    fi
}

# Check if LocalStack is being used
is_localstack() {
    [ -n "$AWS_ENDPOINT_URL" ] && [[ "$AWS_ENDPOINT_URL" == *"localhost"* || "$AWS_ENDPOINT_URL" == *"localstack"* ]]
}

# =========================================================================
# Backup Functions
# =========================================================================

backup_database() {
    local database=$1
    local backup_file="${database}_${TIMESTAMP}.sql.gz"
    local s3_path="s3://${S3_BUCKET}/postgres/${DATE_PREFIX}/${backup_file}"
    
    log "Backing up database: $database"
    
    # Create backup using pg_dump and compress
    pg_dump \
        -h "$POSTGRES_HOST" \
        -p "$POSTGRES_PORT" \
        -U "$POSTGRES_USER" \
        -d "$database" \
        --format=plain \
        --no-owner \
        --no-acl \
        2>/dev/null | gzip | aws_cmd s3 cp - "$s3_path"
    
    if [ $? -eq 0 ]; then
        log "Successfully backed up $database to $s3_path"
        
        # Record metadata
        local metadata="{\"database\":\"$database\",\"timestamp\":\"$TIMESTAMP\",\"host\":\"$POSTGRES_HOST\",\"size\":\"$(aws_cmd s3 ls "$s3_path" | awk '{print $3}')\"}"
        echo "$metadata" | aws_cmd s3 cp - "s3://${S3_BUCKET}/postgres/metadata/${database}_latest.json"
    else
        error "Failed to backup $database"
    fi
}

backup_all_databases() {
    log "Backing up all databases..."
    
    # List all databases except templates and system DBs
    databases=$(psql \
        -h "$POSTGRES_HOST" \
        -p "$POSTGRES_PORT" \
        -U "$POSTGRES_USER" \
        -d postgres \
        -t -c "SELECT datname FROM pg_database WHERE datistemplate = false AND datname NOT IN ('postgres', 'rdsadmin');" \
        2>/dev/null | tr -d ' ')
    
    for db in $databases; do
        if [ -n "$db" ]; then
            backup_database "$db"
        fi
    done
    
    log "All database backups complete"
}

# =========================================================================
# Restore Functions
# =========================================================================

list_backups() {
    local database=${1:-""}
    
    log "Listing available backups..."
    
    if [ -n "$database" ]; then
        aws_cmd s3 ls "s3://${S3_BUCKET}/postgres/" --recursive | grep "$database" | sort -r | head -20
    else
        aws_cmd s3 ls "s3://${S3_BUCKET}/postgres/" --recursive | grep ".sql.gz" | sort -r | head -20
    fi
}

restore_database() {
    local backup_path=$1
    local target_database=$2
    
    if [ "$backup_path" == "latest" ] && [ -n "$target_database" ]; then
        # Find the latest backup for this database
        backup_path=$(aws_cmd s3 ls "s3://${S3_BUCKET}/postgres/" --recursive | grep "${target_database}_" | sort -r | head -1 | awk '{print $4}')
        if [ -z "$backup_path" ]; then
            error "No backup found for database: $target_database"
        fi
        backup_path="s3://${S3_BUCKET}/${backup_path}"
    fi
    
    log "Restoring from: $backup_path"
    log "Target database: $target_database"
    
    # Download and restore
    aws_cmd s3 cp "$backup_path" - | gunzip | psql \
        -h "$POSTGRES_HOST" \
        -p "$POSTGRES_PORT" \
        -U "$POSTGRES_USER" \
        -d "$target_database"
    
    if [ $? -eq 0 ]; then
        log "Successfully restored $target_database from $backup_path"
    else
        error "Failed to restore $target_database"
    fi
}

# =========================================================================
# Cleanup Functions
# =========================================================================

cleanup_old_backups() {
    log "Cleaning up backups older than $BACKUP_RETENTION_DAYS days..."
    
    # Calculate cutoff date
    if [[ "$OSTYPE" == "darwin"* ]]; then
        cutoff_date=$(date -v-${BACKUP_RETENTION_DAYS}d +%Y-%m-%d)
    else
        cutoff_date=$(date -d "-${BACKUP_RETENTION_DAYS} days" +%Y-%m-%d)
    fi
    
    log "Cutoff date: $cutoff_date"
    
    # List and delete old backups
    aws_cmd s3 ls "s3://${S3_BUCKET}/postgres/" --recursive | while read line; do
        file_date=$(echo "$line" | awk '{print $1}')
        file_path=$(echo "$line" | awk '{print $4}')
        
        if [[ "$file_date" < "$cutoff_date" ]] && [[ "$file_path" == *.sql.gz ]]; then
            log "Deleting old backup: $file_path"
            aws_cmd s3 rm "s3://${S3_BUCKET}/${file_path}"
        fi
    done
    
    log "Cleanup complete"
}

# =========================================================================
# Main
# =========================================================================

show_usage() {
    cat << EOF
Ravenhelm Database Backup Script

Usage:
  $0 [command] [options]

Commands:
  backup [database]     Backup database(s) to S3 (default: all)
  restore <path> <db>   Restore from S3 backup
  list [database]       List available backups
  cleanup               Remove old backups

Options:
  --help               Show this help message

Environment:
  AWS_ENDPOINT_URL     LocalStack endpoint (default: http://localhost:4566)
  POSTGRES_HOST        PostgreSQL host (default: localhost)
  POSTGRES_PORT        PostgreSQL port (default: 5432)
  POSTGRES_USER        PostgreSQL user (default: postgres)
  PGPASSWORD           PostgreSQL password (required)
  S3_BUCKET            Target S3 bucket (default: ravenhelm-backups)

Examples:
  # Backup all databases to LocalStack
  $0 backup

  # Backup specific database
  $0 backup hlidskjalf

  # Restore latest backup
  $0 restore latest hlidskjalf

  # List backups
  $0 list

  # Cleanup old backups
  $0 cleanup
EOF
}

main() {
    local command=${1:-"backup"}
    shift 2>/dev/null || true
    
    case "$command" in
        backup)
            if [ -n "$1" ]; then
                backup_database "$1"
            else
                backup_all_databases
            fi
            ;;
        restore)
            if [ -z "$1" ] || [ -z "$2" ]; then
                error "Usage: $0 restore <backup_path|latest> <target_database>"
            fi
            restore_database "$1" "$2"
            ;;
        list)
            list_backups "$1"
            ;;
        cleanup)
            cleanup_old_backups
            ;;
        --help|-h)
            show_usage
            ;;
        *)
            error "Unknown command: $command. Use --help for usage."
            ;;
    esac
}

# Check prerequisites
check_prerequisites() {
    # Check for required commands
    for cmd in pg_dump psql aws gzip; do
        if ! command -v $cmd &> /dev/null; then
            error "Required command not found: $cmd"
        fi
    done
    
    # Check for PGPASSWORD
    if [ -z "$PGPASSWORD" ]; then
        log "Warning: PGPASSWORD not set. You may be prompted for password."
    fi
    
    # Check S3 bucket exists
    if ! aws_cmd s3 ls "s3://${S3_BUCKET}" &>/dev/null; then
        log "Creating S3 bucket: $S3_BUCKET"
        aws_cmd s3 mb "s3://${S3_BUCKET}"
    fi
}

# Run
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    check_prerequisites
    main "$@"
fi

