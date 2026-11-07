# Production Infrastructure & Resource Sizing Guide

**Product:** Predictive DevOps Intelligence Platform  
**Architecture:** Decoupled Micro-Workloads (API, Stream Worker, Frontend, Database, Message Broker)  

---

## 1. Workload Sizing Matrix

### Sizing Profiles

| Component | Profile | Replicas | CPU Requests | CPU Limits | Memory Requests | Memory Limits |
|---|---|---|---|---|---|---|
| **Backend API** | Small (Dev) | 1 | 100m | 500m | 256Mi | 512Mi |
| | Medium (Staging) | 2 | 250m | 1000m | 512Mi | 1024Mi |
| | **Large (Production)** | **3 – 10 (HPA)** | **500m** | **2000m** | **1024Mi** | **2048Mi** |
| **Stream Worker** | Small (Dev) | 1 | 100m | 500m | 256Mi | 512Mi |
| | Medium (Staging) | 2 | 250m | 1000m | 512Mi | 1024Mi |
| | **Large (Production)** | **2 – 8 (HPA)** | **500m** | **1500m** | **1024Mi** | **2048Mi** |
| **Frontend UI** | Small (Dev) | 1 | 50m | 250m | 128Mi | 256Mi |
| | Medium (Staging) | 2 | 100m | 500m | 128Mi | 512Mi |
| | **Large (Production)** | **3** | **250m** | **1000m** | **256Mi** | **1024Mi** |
| **PostgreSQL 16** | Production | 1 (or HA pair) | 2000m | 4000m | 4096Mi | 8192Mi |
| **Redis 7.2** | Production | 1 (or Cluster) | 500m | 1000m | 1024Mi | 2048Mi |

---

## 2. PostgreSQL Connection Pool Calculations

To prevent connection starvation on PostgreSQL:

$$\text{Total Connections} = (N_{\text{backend}} \times \text{pool\_size}) + (N_{\text{worker}} \times \text{pool\_size}) + \text{buffer}$$

In our hardened production configuration:
- `backend`: `pool_size = 15`, `max_overflow = 25` (max 40 per pod).
- At standard baseline (3 backend pods + 3 worker pods):
  $$3 \times 15 + 3 \times 15 = 90\text{ connections}$$
- Under maximum HPA scale (10 backend pods + 8 worker pods):
  $$10 \times 15 + 8 \times 15 = 270\text{ connections}$$
- **PostgreSQL Requirement:** `max_connections` in `postgresql.conf` should be configured to **$\ge 400$** or managed through PgBouncer / RDS Proxy.

---

## 3. Horizontal Pod Autoscaler (HPA) Policy

```yaml
metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 75%
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80%
```

- **Scale-Up Rule:** Add pods when average CPU exceeds 75% over a 3-minute window or memory exceeds 80%.
- **Scale-Down Stabilization Window:** 300 seconds (5 minutes) to prevent flapping / thrashing during traffic bursts.

---

## 4. Redis Memory & Eviction Tuning

- **Stream Retention:** Max length of `stream:devops:events` capped with `XADD MAXLEN ~ 500000` to prevent unbounded memory growth.
- **Maxmemory Policy:** `volatile-lru` or `noeviction` on stream databases so operational signals are not silently evicted.
