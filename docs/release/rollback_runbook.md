# Production Rollback Runbook (V1.0)

**Scope:** Zero-downtime rolling container rollbacks, database schema rollbacks, and poison pill recovery.

---

## 1. Fast Rollback (Container Image Level)

If an application regression is identified post-rollout:

```bash
# Rollback backend API
kubectl rollout undo deployment/backend -n devops-intelligence
kubectl rollout status deployment/backend -n devops-intelligence

# Rollback background worker
kubectl rollout undo deployment/worker -n devops-intelligence
kubectl rollout status deployment/worker -n devops-intelligence

# Rollback frontend UI
kubectl rollout undo deployment/frontend -n devops-intelligence
kubectl rollout status deployment/frontend -n devops-intelligence
```

---

## 2. Database Schema Rollback

In accordance with backward-compatible schema expansion principles, if an Alembic migration must be rolled back:

```bash
# 1. Scale down application workers
kubectl scale deployment/backend --replicas=0 -n devops-intelligence
kubectl scale deployment/worker --replicas=0 -n devops-intelligence

# 2. Run Alembic downgrade
kubectl run alembic-downgrade-job \
  --namespace devops-intelligence \
  --image=devops-intelligence-backend:latest \
  --restart=Never \
  --env-from=configMap/platform-config \
  --env-from=secret/platform-secrets \
  -- command -- alembic downgrade -1

# 3. Wait for completion and check logs
kubectl logs pod/alembic-downgrade-job -n devops-intelligence

# 4. Re-deploy previous application revision and restore replicas
kubectl rollout undo deployment/backend -n devops-intelligence
kubectl scale deployment/backend --replicas=3 -n devops-intelligence
kubectl scale deployment/worker --replicas=3 -n devops-intelligence
```

---

## 3. Emergency Safe Mode (Fail-Closed)

To immediately pause agent risk evaluations while maintaining event recording:
```bash
kubectl patch configmap platform-config -n devops-intelligence --type merge -p '{"data":{"AUTO_TRIGGER_RISK_ASSESSMENT":"false"}}'
kubectl rollout restart deployment/backend -n devops-intelligence
```
