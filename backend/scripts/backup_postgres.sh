#!/usr/bin/env bash
# ==============================================================================
# POSTGRESQL AUTOMATED BACKUP SCRIPT WITH RETENTION POLICY
# ==============================================================================
# Performs transactional, consistent backup of the PostgreSQL database using pg_dump.
# Compresses output with gzip, computes SHA-256 integrity checksum, and enforces
# rolling retention (default: keep 30 days of daily backups).
# ==============================================================================

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-devops_intelligence}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

TIMESTAMP=$(date -u +"%Y%m%d_%H%M%SZ")
BACKUP_FILE="${BACKUP_DIR}/${POSTGRES_DB}_backup_${TIMESTAMP}.sql.gz"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"

mkdir -p "${BACKUP_DIR}"

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Starting consistent database backup for ${POSTGRES_DB} on ${POSTGRES_HOST}:${POSTGRES_PORT}..."

# Export PGPASSWORD if provided in environment
if [ -n "${POSTGRES_PASSWORD:-}" ]; then
  export PGPASSWORD="${POSTGRES_PASSWORD}"
fi

# Execute pg_dump with custom/directory or gzipped plain SQL format
pg_dump \
  --host="${POSTGRES_HOST}" \
  --port="${POSTGRES_PORT}" \
  --username="${POSTGRES_USER}" \
  --dbname="${POSTGRES_DB}" \
  --format=plain \
  --no-owner \
  --no-privileges \
  | gzip -9 > "${BACKUP_FILE}"

# Generate cryptographic SHA-256 checksum for audit and integrity verification
sha256sum "${BACKUP_FILE}" | awk '{print $1}' > "${CHECKSUM_FILE}"

BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Backup successful: ${BACKUP_FILE} (${BACKUP_SIZE})"
echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] SHA-256 checksum: $(cat "${CHECKSUM_FILE}")"

# Retention Policy: Prune backups older than RETENTION_DAYS
echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Enforcing retention policy: deleting backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "${POSTGRES_DB}_backup_*.sql.gz" -mtime +"${RETENTION_DAYS}" -delete
find "${BACKUP_DIR}" -name "${POSTGRES_DB}_backup_*.sha256" -mtime +"${RETENTION_DAYS}" -delete

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Backup routine completed successfully."
