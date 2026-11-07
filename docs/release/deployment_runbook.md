# Production Deployment Runbook (V1.0)

**Target Environment:** Kubernetes 1.28+ (EKS, GKE, AKS, Bare-Metal)  
**Configuration Management:** Kustomize (`kubectl apply -k`)  

---

## 1. Step-by-Step Rollout Workflow

### Step 1: Pre-Flight Check
```bash
# Verify kubectl connection and client/server version
kubectl version
kubectl cluster-info

# Ensure namespace exists
kubectl apply -f infrastructure/kubernetes/base/namespace.yaml
```

### Step 2: Inject Platform Secrets
```bash
kubectl apply -f infrastructure/kubernetes/base/secrets.example.yaml # Replace with production credentials via Vault/SealedSecrets
```

### Step 3: Run Database Migrations
Decoupled schema migrations must be applied before rolling out updated application pods:
```bash
kubectl apply -f infrastructure/kubernetes/base/migration-job.yaml
kubectl wait --for=condition=complete --timeout=120s job/db-migration-job -n devops-intelligence
```

### Step 4: Deploy Production Overlays
```bash
kubectl apply -k infrastructure/kubernetes/overlays/production
```

### Step 5: Verify Rollout Status
```bash
kubectl rollout status deployment/backend -n devops-intelligence --timeout=180s
kubectl rollout status deployment/worker -n devops-intelligence --timeout=180s
kubectl rollout status deployment/frontend -n devops-intelligence --timeout=180s
```

### Step 6: Verify Health Probes
```bash
kubectl get pods -n devops-intelligence -l app.kubernetes.io/name=backend
kubectl exec -it deploy/backend -n devops-intelligence -- curl -s http://localhost:8000/api/v1/health/liveness
kubectl exec -it deploy/backend -n devops-intelligence -- curl -s http://localhost:8000/api/v1/health/readiness
```
