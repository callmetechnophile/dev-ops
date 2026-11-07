# Operational Rollback & Incident Runbooks

**Product:** Predictive DevOps Intelligence Platform  
**Target Environment:** Kubernetes Production  

---

## 1. Application Deployment Rollback

If a new container image causes regressions, crashes, or elevated error rates, execute an immediate zero-downtime rolling rollback.

### Rollback Commands

```bash
# Roll back backend API deployment
kubectl rollout undo deployment/backend -n devops-intelligence
kubectl rollout status deployment/backend -n devops-intelligence

# Roll back background stream worker deployment
kubectl rollout undo deployment/worker -n devops-intelligence
kubectl rollout status deployment/worker -n devops-intelligence

# Roll back frontend UI deployment
kubectl rollout undo deployment/frontend -n devops-intelligence
kubectl rollout status deployment/frontend -n devops-intelligence
```

### Inspect Rollout History

```bash
kubectl rollout history deployment/backend -n devops-intelligence
kubectl rollout history deployment/worker -n devops-intelligence
```

---

## 2. Decoupled Database Rollback Runbook

### Schema Backward-Compatibility Invariant
- **Rule:** Every schema change must follow the expand/contract pattern. Existing columns and tables must not be dropped in the same release as application updates.
- If a database migration rollback is unavoidable:

```bash
# 1. Scale down backend and worker pods to 0 to prevent concurrent writes during schema mutation
kubectl scale deployment/backend --replicas=0 -n devops-intelligence
kubectl scale deployment/worker --replicas=0 -n devops-intelligence

# 2. Run Alembic downgrade one revision
kubectl run db-rollback-job \
  --namespace devops-intelligence \
  --image=devops-intelligence-backend:latest \
  --restart=Never \
  --env-from=configMap/platform-config \
  --env="SYNC_DATABASE_URL=postgresql+psycopg2://postgres:<SECURE_PASSWORD>@postgres-service:5432/devops_intelligence" \
  -- command -- alembic downgrade -1

# 3. Verify Alembic current version
kubectl logs pod/db-rollback-job -n devops-intelligence

# 4. Roll back application deployment to compatible image and restore replicas
kubectl rollout undo deployment/backend -n devops-intelligence
kubectl scale deployment/backend --replicas=3 -n devops-intelligence
kubectl scale deployment/worker --replicas=3 -n devops-intelligence
```

---

## 3. Redis Stream Recovery & Poison Pill Quarantine

When malformed payloads trigger repeated consumer crashes:

1. **Dead-Letter Inspection:** Messages exceeding 3 failed delivery attempts are automatically routed to `stream:devops:deadletter` by `RedisStreamWorker`.
2. **Inspect Poison Pills:**
   ```bash
   kubectl exec -it deploy/redis -n devops-intelligence -- redis-cli XRANGE stream:devops:deadletter - + COUNT 10
   ```
3. **Consumer Lag Recovery:**
   - To force claim stuck pending messages:
   ```bash
   # Inspect pending entries
   kubectl exec -it deploy/redis -n devops-intelligence -- redis-cli XPENDING stream:devops:events group:devops:intelligence
   ```

---

## 4. Emergency Fail-Safe & Agent Lockdown

The agent is strictly **recommendation-only** and cannot modify production clusters. If false-positive risk assessments or policy anomalies occur:

### Maintenance Mode (Fail-Closed)
- When in doubt, all deployments with high risk require explicit human approval.
- To temporarily halt automated webhook risk assessments without stopping event recording:
  ```bash
  kubectl patch configmap platform-config -n devops-intelligence --type merge -p '{"data":{"AUTO_TRIGGER_RISK_ASSESSMENT":"false"}}'
  kubectl rollout restart deployment/backend -n devops-intelligence
  ```
