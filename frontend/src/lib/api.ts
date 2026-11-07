const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

export async function fetchGitHubStatus() {
  const res = await fetch(`${API_BASE}/integrations/github/status`, { cache: "no-store" });
  if (!res.ok) throw new Error("GitHub status check failed");
  return res.json();
}

export async function fetchRepositories() {
  const res = await fetch(`${API_BASE}/repositories`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch repositories");
  return res.json();
}

export async function fetchRepository(id: string) {
  const res = await fetch(`${API_BASE}/repositories/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Repository ${id} not found`);
  return res.json();
}

export async function fetchRepositoryCommits(id: string) {
  const res = await fetch(`${API_BASE}/repositories/${id}/commits`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch repository commits");
  return res.json();
}

export async function fetchWorkflows(repositoryId?: string) {
  const url = repositoryId ? `${API_BASE}/workflows?repository_id=${repositoryId}` : `${API_BASE}/workflows`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch workflows");
  return res.json();
}

export async function fetchWorkflow(id: string) {
  const res = await fetch(`${API_BASE}/workflows/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Workflow ${id} not found`);
  return res.json();
}

export async function fetchBuilds(repositoryId?: string) {
  const url = repositoryId ? `${API_BASE}/builds?repository_id=${repositoryId}` : `${API_BASE}/builds`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch builds");
  return res.json();
}

export async function fetchBuild(id: string) {
  const res = await fetch(`${API_BASE}/builds/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Build ${id} not found`);
  return res.json();
}

export async function fetchDeployments(status?: string) {
  const url = status ? `${API_BASE}/deployments?status=${status}` : `${API_BASE}/deployments`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch deployments");
  return res.json();
}

export async function fetchDeployment(id: string) {
  const res = await fetch(`${API_BASE}/deployments/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Deployment ${id} not found`);
  return res.json();
}

export async function fetchDeploymentTimeline(id: string) {
  const res = await fetch(`${API_BASE}/deployments/${id}/timeline`, { cache: "no-store" });
  if (!res.ok) return null;
  return res.json();
}

export async function fetchDeploymentRisk(id: string) {
  const res = await fetch(`${API_BASE}/deployments/${id}/risk`, { cache: "no-store" });
  if (!res.ok) return null;
  return res.json();
}

// --- Milestone 3 Incident & Failure Memory APIs ---

export async function fetchIncidents(params?: { status?: string; severity?: string; environment?: string }) {
  let url = `${API_BASE}/incidents`;
  const query = new URLSearchParams();
  if (params?.status) query.append("status", params.status);
  if (params?.severity) query.append("severity", params.severity);
  if (params?.environment) query.append("environment", params.environment);
  if (query.toString()) url += `?${query.toString()}`;

  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch incidents");
  return res.json();
}

export async function fetchIncident(id: string) {
  const res = await fetch(`${API_BASE}/incidents/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Incident ${id} not found`);
  return res.json();
}

export async function fetchIncidentAnalytics() {
  const res = await fetch(`${API_BASE}/incidents/analytics`, { cache: "no-store" });
  if (!res.ok) return null;
  return res.json();
}

export async function fetchIncidentTimeline(id: string) {
  const res = await fetch(`${API_BASE}/incidents/${id}/timeline`, { cache: "no-store" });
  if (!res.ok) return null;
  return res.json();
}

export async function fetchIncidentClassifications(id: string) {
  const res = await fetch(`${API_BASE}/incidents/${id}/classifications`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchIncidentHypotheses(id: string) {
  const res = await fetch(`${API_BASE}/incidents/${id}/hypotheses`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function confirmHypothesis(
  incidentId: string,
  hypothesisId: string,
  data: {
    confirmed_by: string;
    confirmation_notes: string;
    root_cause_summary: string;
    verified_engineering_lesson: string;
    prevention_strategy: string;
  }
) {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/hypotheses/${hypothesisId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to confirm root cause hypothesis");
  }
  return res.json();
}

export async function rejectHypothesis(
  incidentId: string,
  hypothesisId: string,
  data: { rejected_by: string; rejection_reason: string }
) {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/hypotheses/${hypothesisId}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to reject hypothesis");
  }
  return res.json();
}

export async function markInsufficientEvidence(
  incidentId: string,
  hypothesisId: string,
  data: { reviewed_by: string; notes: string }
) {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/hypotheses/${hypothesisId}/insufficient-evidence`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to mark hypothesis as insufficient evidence");
  }
  return res.json();
}

export async function fetchIncidentRemediations(id: string) {
  const res = await fetch(`${API_BASE}/incidents/${id}/remediations`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function recordIncidentRemediation(
  incidentId: string,
  data: {
    action_type: string;
    description: string;
    proposed_by?: string;
    approved_by?: string;
    execution_status?: string;
    outcome?: string;
    effectiveness?: string;
    runbook_url?: string;
  }
) {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/remediations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to record remediation action");
  }
  return res.json();
}

export async function fetchSimilarIncidents(incidentId: string) {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/similar`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchOperationalLessons() {
  const res = await fetch(`${API_BASE}/memory/lessons`, { cache: "no-store" });
  if (!res.ok) return { items: [] };
  return res.json();
}

export async function searchMemory(query: string, category?: string, environment?: string) {
  let url = `${API_BASE}/memory/search?q=${encodeURIComponent(query)}`;
  if (category) url += `&category=${encodeURIComponent(category)}`;
  if (environment) url += `&environment=${encodeURIComponent(environment)}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("Memory search failed");
  return res.json();
}

// --- End Milestone 3 APIs ---

export async function fetchServices() {
  const res = await fetch(`${API_BASE}/services`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch services");
  return res.json();
}

export async function fetchServiceDependencies(serviceId: string) {
  const res = await fetch(`${API_BASE}/services/${serviceId}/dependencies`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch dependencies");
  return res.json();
}

export async function submitApproval(requestId: string, decision: "APPROVED" | "REJECTED", justification: string, userId: string) {
  return submitApprovalDecision(requestId, decision, justification, userId);
}

export async function fetchEvents() {
  const res = await fetch(`${API_BASE}/events`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch events");
  return res.json();
}

// --- Milestone 4 Predictive Risk Intelligence APIs ---

export async function fetchRiskAssessments(params?: { service_id?: string; risk_level?: string; environment?: string }) {
  let url = `${API_BASE}/risk/assessments`;
  const query = new URLSearchParams();
  if (params?.service_id) query.append("service_id", params.service_id);
  if (params?.risk_level) query.append("risk_level", params.risk_level);
  if (params?.environment) query.append("environment", params.environment);
  if (query.toString()) url += `?${query.toString()}`;

  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch risk assessments");
  return res.json();
}

export async function fetchRiskAssessment(id: string) {
  const res = await fetch(`${API_BASE}/risk/assessments/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Risk assessment ${id} not found`);
  return res.json();
}

export async function triggerRiskAssessment(deploymentId: string) {
  const res = await fetch(`${API_BASE}/risk/assessments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ deployment_id: deploymentId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to trigger risk assessment");
  }
  return res.json();
}

export async function fetchRiskExplanation(id: string) {
  const res = await fetch(`${API_BASE}/risk/assessments/${id}/explanation`, { cache: "no-store" });
  if (!res.ok) return null;
  return res.json();
}

export async function fetchRiskSimilarIncidents(id: string) {
  const res = await fetch(`${API_BASE}/risk/assessments/${id}/similar-incidents`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchModelStatus() {
  const res = await fetch(`${API_BASE}/risk/models/status`, { cache: "no-store" });
  if (!res.ok) return null;
  return res.json();
}

export async function fetchModels() {
  const res = await fetch(`${API_BASE}/risk/models`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchModelEvaluation(version: string) {
  const res = await fetch(`${API_BASE}/risk/models/${version}/evaluation`, { cache: "no-store" });
  if (!res.ok) return null;
  return res.json();
}

export async function triggerModelTraining() {
  const res = await fetch(`${API_BASE}/risk/models/train`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Model training failed");
  }
  return res.json();
}

export async function fetchDeploymentImpact(deploymentId: string) {
  const res = await fetch(`${API_BASE}/risk/impact/${deploymentId}`, { cache: "no-store" });
  if (!res.ok) return null;
  return res.json();
}

// --------------------------------------------------------------------------
// Milestone 5: Agent Orchestration, Policies & Approvals
// --------------------------------------------------------------------------

export async function fetchAgentExecutions(params?: {
  status?: string;
  state?: string;
  environment?: string;
  page?: number;
  page_size?: number;
}) {
  let url = `${API_BASE}/agent/executions`;
  const query = new URLSearchParams();
  if (params?.status) query.append("status", params.status);
  if (params?.state) query.append("state", params.state);
  if (params?.environment) query.append("environment", params.environment);
  if (params?.page) query.append("page", String(params.page));
  if (params?.page_size) query.append("page_size", String(params.page_size));
  if (query.toString()) url += `?${query.toString()}`;

  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch agent executions");
  return res.json();
}

export async function fetchAgentExecution(id: string) {
  const res = await fetch(`${API_BASE}/agent/executions/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Agent execution ${id} not found`);
  return res.json();
}

export async function triggerAgentExecution(deploymentId: string, triggerType = "MANUAL_DISPATCH") {
  const res = await fetch(`${API_BASE}/agent/executions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ deployment_id: deploymentId, trigger_type: triggerType }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to trigger agent execution");
  }
  return res.json();
}

export async function fetchExecutionTimeline(id: string) {
  const res = await fetch(`${API_BASE}/agent/executions/${id}/timeline`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchExecutionRecommendations(id: string) {
  const res = await fetch(`${API_BASE}/agent/executions/${id}/recommendations`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchExecutionPolicyEvaluations(id: string) {
  const res = await fetch(`${API_BASE}/agent/executions/${id}/policy-evaluations`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchExecutionOutcomes(id: string) {
  const res = await fetch(`${API_BASE}/agent/executions/${id}/outcomes`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function advanceExecutionOutcome(id: string, observationWindowMinutes = 60) {
  const res = await fetch(`${API_BASE}/agent/executions/${id}/advance-outcome?observation_window_minutes=${observationWindowMinutes}`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to advance execution outcome");
  }
  return res.json();
}

export async function fetchDeploymentPolicies() {
  const res = await fetch(`${API_BASE}/agent/policies`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function createDeploymentPolicy(policy: {
  name: string;
  description?: string;
  policy_version?: string;
  enabled?: boolean;
  policy_definition: Record<string, any>;
}) {
  const res = await fetch(`${API_BASE}/agent/policies`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(policy),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to create deployment policy");
  }
  return res.json();
}

export async function updateDeploymentPolicy(id: string, updates: Record<string, any>) {
  const res = await fetch(`${API_BASE}/agent/policies/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to update deployment policy");
  }
  return res.json();
}

export async function fetchApprovals(params?: { status?: string; page?: number; page_size?: number }) {
  let url = `${API_BASE}/approvals`;
  const query = new URLSearchParams();
  if (params?.status) query.append("status", params.status);
  if (params?.page) query.append("page", String(params.page));
  if (params?.page_size) query.append("page_size", String(params.page_size));
  if (query.toString()) url += `?${query.toString()}`;

  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch approvals");
  return res.json();
}

export async function fetchApproval(id: string) {
  const res = await fetch(`${API_BASE}/approvals/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Approval ${id} not found`);
  return res.json();
}

export async function submitApprovalDecision(id: string, action: string, notes: string, userId?: string) {
  const res = await fetch(`${API_BASE}/approvals/${id}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, notes, user_id: userId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to record approval decision");
  }
  return res.json();
}
