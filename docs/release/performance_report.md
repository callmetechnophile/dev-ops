# Performance and Capacity Benchmark Report

**Benchmark Date:** 2026-11-07  
**Environment:** Python 3.13.9, SQLite/PostgreSQL Engine, In-Memory Async Session Pool  
**Benchmark Script:** `backend/scripts/run_benchmarks.py`  
**Raw Telemetry Record:** `docs/release/benchmark_results.json`  

---

## 1. Measured Performance Results

### A. Burst Webhook Ingestion (100 Requests, Concurrency 10)
- **Total Duration:** 0.961 seconds
- **Throughput:** **104.0 requests/second**
- **Error Rate:** **0.0% (0 errors)**
- **p50 Latency:** **93.05 ms**
- **p95 Latency:** **107.12 ms**
- **p99 Latency:** **118.06 ms**

### B. Concurrent Read API (150 Requests, Concurrency 15)
- **Total Duration:** 0.683 seconds
- **Throughput:** **219.6 requests/second**
- **Error Rate:** **0.0% (0 errors)**
- **p50 Latency:** **60.83 ms**
- **p95 Latency:** **102.88 ms**
- **p99 Latency:** **128.58 ms**

### C. Database Query Latency (50 Direct Queries)
- **p50 Latency:** **2.71 ms**
- **p95 Latency:** **3.77 ms**
- **p99 Latency:** **4.56 ms**

### D. Process Resource Footprint
- **Resident Set Size (RSS Memory):** **286.9 MB**
- **Peak CPU Utilization:** **18.5%**

---

## 2. Capacity Sizing & Proposed SLO Targets

Based on the measured baselines, the platform comfortably meets enterprise operational thresholds:

| Service Level Objective (SLO) | Target | Measured Baseline | Compliance |
|---|---|---|---|
| **Webhook Processing Latency (p95)** | $< 250\text{ ms}$ | **$107.12\text{ ms}$** | **MET (57% headroom)** |
| **API Read Latency (p95)** | $< 200\text{ ms}$ | **$102.88\text{ ms}$** | **MET (48% headroom)** |
| **Database Query Latency (p95)** | $< 15\text{ ms}$ | **$3.77\text{ ms}$** | **MET (75% headroom)** |
| **Ingestion Error Rate** | $< 0.1\%$ | **$0.00\%$** | **MET (Zero errors)** |
