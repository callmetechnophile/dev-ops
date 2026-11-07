# Backup and Disaster Recovery (DR) Plan

**Product:** Predictive DevOps Intelligence Platform  
**RPO (Recovery Point Objective):** $\le 15\text{ minutes}$  
**RTO (Recovery Time Objective):** $\le 30\text{ minutes}$  

---

## 1. Data Classification & Persistence Strategy

| Subsystem | Storage Mechanism | Backup Method | Frequency | Retention |
|---|---|---|---|---|
| **PostgreSQL & Vector** | Persistent Volume (20Gi PVC) | `pg_dump` compressed + SHA-256 Checksum | Daily Automated + Pre-migration | 30 Days |
| **Redis Streams** | Append-Only File (AOF) + RDB | RDB Snapshots on PVC | Hourly snapshots | 7 Days |
| **Configuration** | Git Repository / Kustomize | Version-controlled Git commit | Continuous | Permanent |

---

## 2. Automated PostgreSQL Backup Procedure

The script `backend/scripts/backup_postgres.sh` executes consistent atomic backups:

1. **Creates gzip archive:** Generates `postgres_backup_YYYYMMDD_HHMMSS.sql.gz`.
2. **Generates SHA-256 Checksum:** Stores `postgres_backup_YYYYMMDD_HHMMSS.sql.gz.sha256`.
3. **Prunes Stale Backups:** Deletes backups older than 30 days.

### Triggering Manual Backup

```bash
# Execute from within postgres container or via backup cronjob
./backend/scripts/backup_postgres.sh
```

---

## 3. Disaster Recovery Restore Procedure

The restore script `backend/scripts/restore_postgres.sh` enforces strict integrity checks prior to restoring:

```bash
# Syntax: ./backend/scripts/restore_postgres.sh <backup_file.sql.gz>
./backend/scripts/restore_postgres.sh /var/backups/postgres/postgres_backup_20261107_210000.sql.gz
```

### Restore Verification Checklist:
1. Verifies SHA-256 checksum against `.sha256` manifest.
2. Terminates active client connections on `devops_intelligence`.
3. Recreates clean database schema with `vector` and `uuid-ossp` extensions.
4. Executes `gunzip` and streams SQL commands into `psql`.
5. Runs verification query `SELECT count(*) FROM incidents;` and `SELECT count(*) FROM deployments;`.

---

## 4. Cold Standby & Multi-Region Recovery Runbook

In the event of total datacenter or cloud region failure:

1. **Provision Kubernetes Cluster:** Spin up secondary EKS/GKE cluster in target region (`us-west-2` or `eu-west-1`).
2. **Provision Storage & Secrets:** Apply `infrastructure/kubernetes/base/namespace.yaml` and inject `platform-secrets`.
3. **Download Latest Backup from S3 / Cold Storage:**
   ```bash
   aws s3 sync s3://company-devops-intel-backups/postgres/ /var/backups/postgres/
   ```
4. **Restore Database:**
   ```bash
   ./backend/scripts/restore_postgres.sh /var/backups/postgres/latest.sql.gz
   ```
5. **Apply Kustomize Production Overlay:**
   ```bash
   kubectl apply -k infrastructure/kubernetes/overlays/production
   ```
6. **Switch DNS Ingress:** Update Route53 / Cloudflare DNS A/CNAME record to the new Ingress Load Balancer IP.
