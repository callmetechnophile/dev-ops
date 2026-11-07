# Backup and Recovery Runbook (V1.0)

**RPO:** $\le 15$ minutes  
**RTO:** $\le 30$ minutes  

---

## 1. Daily Automated Backup Execution

Backups are executed by `backend/scripts/backup_postgres.sh`:

```bash
# Triggers full consistent database dump with SHA-256 checksum and gzip compression
./backend/scripts/backup_postgres.sh
```

**Artifacts Generated:**
- `/var/backups/postgres/postgres_backup_YYYYMMDD_HHMMSS.sql.gz`
- `/var/backups/postgres/postgres_backup_YYYYMMDD_HHMMSS.sql.gz.sha256`

---

## 2. Disaster Recovery Database Restoration

To restore from a backup archive:

```bash
# Syntax: ./backend/scripts/restore_postgres.sh <BACKUP_PATH>
./backend/scripts/restore_postgres.sh /var/backups/postgres/postgres_backup_20261107_210000.sql.gz
```

**Automated Verification Steps Performed:**
1. Verifies SHA-256 checksum against accompanying `.sha256` file. If mismatch, halts immediately.
2. Drops and recreates the target database with `vector` and `uuid-ossp` extensions.
3. Streams decompressed SQL dump via `psql`.
4. Executes row-count integrity checks on `deployments`, `incidents`, and `operational_lessons`.
