# Production Kubernetes Deployment Guide

**Product:** Predictive DevOps Intelligence Platform  
**Target Environment:** Kubernetes 1.28+ (AWS EKS, GCP GKE, Azure AKS, or Bare-Metal K8s)  
**Configuration Management:** Kustomize (Native `kubectl -k`)  

---

## 1. Prerequisites & Cluster Requirements

Before deploying the platform, ensure the following infrastructure operators and prerequisites are provisioned in your cluster:

1. **Kubernetes Version:** `>= v1.28.0`
2. **Ingress Controller:** Ingress-NGINX Controller with SSL termination (`cert-manager` recommended for automated Let's Encrypt certificates).
3. **StorageClass:** A dynamic volume provisioner (e.g. `gp3` on AWS, `standard-rwo` on GKE) supporting `ReadWriteOnce`.
4. **Metrics Server:** Kubernetes `metrics-server` installed for HPA autoscaling.
5. **PostgreSQL & Redis:**
   - Production recommendation: Managed cloud databases (AWS RDS PostgreSQL 16 + ElastiCache Redis 7.2) or use the hardened containerized stateful sets provided in `infrastructure/kubernetes/base/`.
   - Required PostgreSQL extensions: `uuid-ossp`, `vector` (`pgvector/pgvector:pg16`).

---

## 2. Secrets Management & Provisioning

Create a sealed or native secret in the target namespace `devops-intelligence`:

```bash
kubectl create namespace devops-intelligence

kubectl create secret generic platform-secrets \
  --namespace devops-intelligence \
  --from-literal=SECRET_KEY="<GENERATE_64_CHAR_HEX_KEY>" \
  --from-literal=POSTGRES_USER="postgres" \
  --from-literal=POSTGRES_PASSWORD="<SECURE_DB_PASSWORD>" \
  --from-literal=POSTGRES_DB="devops_intelligence" \
  --from-literal=DATABASE_URL="postgresql+asyncpg://postgres:<SECURE_DB_PASSWORD>@postgres-service:5432/devops_intelligence" \
  --from-literal=SYNC_DATABASE_URL="postgresql+psycopg2://postgres:<SECURE_DB_PASSWORD>@postgres-service:5432/devops_intelligence" \
  --from-literal=REDIS_URL="redis://redis-service:6379/0" \
  --from-literal=GITHUB_WEBHOOK_SECRET="<WEBHOOK_SECRET_HMAC>" \
  --from-literal=GITHUB_APP_ID="<APP_ID>" \
  --from-literal=GITHUB_APP_INSTALLATION_ID="<INSTALLATION_ID>" \
  --from-literal=GITHUB_APP_PRIVATE_KEY="<PEM_ENCODED_PRIVATE_KEY>"
```

---

## 3. Decoupled Schema Migration Job

Execute database schema migrations prior to updating container images. Migrations are decoupled from application startup:

```bash
# 1. Apply or trigger migration job
kubectl apply -f infrastructure/kubernetes/base/migration-job.yaml

# 2. Wait for successful completion
kubectl wait --for=condition=complete --timeout=180s job/db-migration-job -n devops-intelligence

# 3. Check logs
kubectl logs job/db-migration-job -n devops-intelligence
```

---

## 4. Rollout Application via Kustomize Overlays

The platform uses Kustomize overlays for environment-specific configuration:

| Environment | Overlay Path | Pod Count | Scaling Policy | Ingress Host |
|---|---|---|---|---|
| **Development** | `infrastructure/kubernetes/overlays/dev` | 1 Backend, 1 Worker, 1 Frontend | Static | `devops-intel.dev.local` |
| **Staging** | `infrastructure/kubernetes/overlays/staging` | 2 Backend, 2 Worker, 2 Frontend | Static | `devops-intel.staging.internal` |
| **Production** | `infrastructure/kubernetes/overlays/production` | 3 Backend, 3 Worker, 3 Frontend | HPA (3-10 Pods, CPU 75%, Mem 80%) | `devops-intel.company.com` |

### Production Rollout Command

```bash
# Preview generated manifests
kubectl kustomize infrastructure/kubernetes/overlays/production

# Apply production manifests
kubectl apply -k infrastructure/kubernetes/overlays/production

# Monitor rollout status
kubectl rollout status deployment/backend -n devops-intelligence --timeout=120s
kubectl rollout status deployment/worker -n devops-intelligence --timeout=120s
kubectl rollout status deployment/frontend -n devops-intelligence --timeout=120s
```

---

## 5. Verification & Health Probes

Verify that all pods, services, and probes are operating properly:

```bash
# 1. Inspect running pods
kubectl get pods -n devops-intelligence -o wide

# 2. Test Kubernetes Probes
# Liveness probe
kubectl exec -it deploy/backend -n devops-intelligence -- curl -s http://localhost:8000/api/v1/health/liveness

# Readiness probe
kubectl exec -it deploy/backend -n devops-intelligence -- curl -s http://localhost:8000/api/v1/health/readiness

# Startup probe
kubectl exec -it deploy/backend -n devops-intelligence -- curl -s http://localhost:8000/api/v1/health/startup

# 3. Verify Prometheus metrics exposition
kubectl exec -it deploy/backend -n devops-intelligence -- curl -s http://localhost:8000/metrics | grep http_requests_total
```
