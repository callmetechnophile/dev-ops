# Known Limitations & Operational Boundaries (V1.0)

**Product:** Predictive DevOps Intelligence Platform  
**Release Target:** V1.0.0  

---

## 1. Controlled Scope Limitations

1. **Strict Recommendation-Only Boundary:**
   The agent does not autonomously deploy code, mutate Kubernetes resources, or trigger rollbacks. All interventions require explicit human approval via the Approval Gateway.
2. **Cold-Start ML Eligibility ($N < 50$):**
   Machine Learning predictive models remain inactive until an organization accumulates at least 50 verified historical deployment outcomes. During cold start, the platform operates transparently on the deterministic rule-based risk engine.
3. **Observation Window Requirement (60 Minutes):**
   Deployments finished less than 60 minutes ago are treated as "CENSORED" to prevent false-success labeling caused by delayed failures or late-surfacing production incidents.
4. **Vector Embedding Fallback:**
   When remote embedding APIs (OpenAI / HuggingFace) are not configured, semantic search automatically uses deterministic 384-dimensional lexical hashing vectors with token overlap scoring, ensuring zero unhandled exceptions.
5. **Single GitHub App per Tenant:**
   V1.0 associates one GitHub App installation per tenant organization. Multi-organization repository federation is planned for V1.1.
