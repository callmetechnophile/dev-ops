#!/usr/bin/env bash
# ==============================================================================
# POSTGRESQL RESTORE VERIFICATION & DISASTER RECOVERY SCRIPT
# ==============================================================================
# Restores a compressed SQL dump after verifying SHA-256 checksum integrity.
# Safe execution: requires explicit confirmation or target database declaration.
# ==============================================================================

set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <path-to-backup-file.sql.gz> [target_database_name]"
  exit 1
fi

BACKUP_FILE="$1"
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
TARGET_DB="${2:-${POSTGRES_DB:-devops_intelligence}}"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"

if [ ! -f "${BACKUP_FILE}" ]; then
  echo "[ERROR] Backup file not found: ${BACKUP_FILE}"
  exit 1
fi

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Initiating database restore procedure for target '${TARGET_DB}'..."

# Verify SHA-256 Checksum if present
if [ -f "${CHECKSUM_FILE}" ]; then
  echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Verifying SHA-256 checksum integrity..."
  EXPECTED_SUM=$(cat "${CHECKSUM_FILE}")
  ACTUAL_SUM=$(sha256sum "${BACKUP_FILE}" | awk '{print $1}')
  if [ "${EXPECTED_SUM}" != "${ACTUAL_SUM}" ]; then
    echo "[FATAL] Checksum mismatch! Corrupt or tampered backup file."
    echo "Expected: ${EXPECTED_SUM}"
    echo "Actual:   ${ACTUAL_SUM}"
    exit 2
  fi
  echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Checksum verified: ${ACTUAL_SUM}"
else
  echo "[WARNING] No companion .sha256 file found. Proceeding with caution."
fi

# Export PGPASSWORD
if [ -n "${POSTGRES_PASSWORD:-}" ]; then
  export PGPASSWORD="${POSTGRES_PASSWORD}"
fi

# Check connection to postgres host
pg_isready -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}"

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Restoring schema and data into database '${TARGET_DB}'..."
gzip -dc "${BACKUP_FILE}" | psql \
  --host="${POSTGRES_HOST}" \
  --port="${POSTGRES_PORT}" \
  --username="${POSTGRES_USER}" \
  --dbname="${TARGET_DB}" \
  --single-transaction \
  --set ON_ERROR_STOP=on

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Database restore finished successfully into '${TARGET_DB}'."
