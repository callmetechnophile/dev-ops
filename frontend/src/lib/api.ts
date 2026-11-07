const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
  if (!res.ok) throw new Error("Health check failed");
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

export async function fetchDeploymentRisk(id: string) {
  const res = await fetch(`${API_BASE}/deployments/${id}/risk`, { cache: "no-store" });
  if (!res.ok) return null;
  return res.json();
}

export async function fetchIncidents() {
  const res = await fetch(`${API_BASE}/incidents`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch incidents");
  return res.json();
}

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

export async function searchMemory(query: string) {
  const res = await fetch(`${API_BASE}/memory/search?q=${encodeURIComponent(query)}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Memory search failed");
  return res.json();
}

export async function fetchApprovals() {
  const res = await fetch(`${API_BASE}/approvals`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch approvals");
  return res.json();
}

export async function submitApproval(requestId: string, decision: "APPROVED" | "REJECTED", justification: string, userId: string) {
  const res = await fetch(`${API_BASE}/approvals/${requestId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision, justification, user_id: userId }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Approval decision submission failed");
  }
  return res.json();
}
