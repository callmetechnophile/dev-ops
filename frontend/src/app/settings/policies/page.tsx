"use client";

import React, { useEffect, useState } from "react";
import { 
  ShieldCheck, 
  ShieldAlert, 
  Plus, 
  CheckCircle2, 
  XCircle, 
  Sliders, 
  Info, 
  ToggleLeft, 
  ToggleRight,
  Code2,
  FileCheck
} from "lucide-react";
import { fetchDeploymentPolicies, createDeploymentPolicy, updateDeploymentPolicy } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // New policy form state
  const [formName, setFormName] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formVersion, setFormVersion] = useState("1.0.0");
  const [maxRiskScore, setMaxRiskScore] = useState(0.65);
  const [maxImpactScore, setMaxImpactScore] = useState(0.70);
  const [blockOnP1, setBlockOnP1] = useState(true);
  const [maxBlastRadius, setMaxBlastRadius] = useState(5);
  const [environments, setEnvironments] = useState("production, prod, staging");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await fetchDeploymentPolicies();
      setPolicies(data || []);
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || "Failed to load deployment policies");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleToggle = async (policy: any) => {
    try {
      await updateDeploymentPolicy(policy.id, { enabled: !policy.enabled });
      setSuccessMsg(`Policy '${policy.name}' is now ${!policy.enabled ? "ACTIVE" : "DISABLED"}.`);
      await load();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to update policy");
    }
  };

  const handleCreatePolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim()) {
      setErrorMsg("Policy name is required");
      return;
    }
    setSaving(true);
    setErrorMsg(null);
    try {
      const parsedEnvs = environments
        .split(",")
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean);

      const policyDefinition = {
        max_risk_score: Number(maxRiskScore),
        max_impact_score: Number(maxImpactScore),
        block_on_p1_incidents: blockOnP1,
        max_allowed_blast_radius: Number(maxBlastRadius),
        require_approval_environments: parsedEnvs,
        require_additional_review_tiers: ["tier-1"],
        max_missing_telemetry_fields: 2,
      };

      await createDeploymentPolicy({
        name: formName.trim(),
        description: formDescription.trim(),
        policy_version: formVersion.trim() || "1.0.0",
        enabled: true,
        policy_definition: policyDefinition,
      });

      setSuccessMsg(`Deployment policy '${formName}' created and activated successfully.`);
      setShowCreateModal(false);
      setFormName("");
      setFormDescription("");
      await load();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to create policy");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-emerald-400" />
            Deployment Governance Policies
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Configure deterministic policy thresholds evaluated by the Agent Orchestrator before gating deployments.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-3.5 py-1.5 rounded bg-accent text-accent-foreground text-xs font-semibold flex items-center gap-1.5 hover:bg-accent/90 transition-colors shadow-sm"
        >
          <Plus className="h-3.5 w-3.5" />
          Create Policy
        </button>
      </div>

      {errorMsg && (
        <div className="p-3 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono flex items-center justify-between">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-rose-400 hover:text-rose-200">
            <XCircle className="h-4 w-4" />
          </button>
        </div>
      )}

      {successMsg && (
        <div className="p-3 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-mono flex items-center justify-between">
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-400 hover:text-emerald-200">
            <CheckCircle2 className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Policies List */}
      <div className="space-y-4">
        {loading ? (
          <div className="p-12 text-center text-xs text-muted-foreground font-mono animate-pulse">
            Loading governance policies...
          </div>
        ) : policies.length === 0 ? (
          <div className="p-12 text-center border border-dashed border-border rounded-lg bg-card/20 space-y-2 font-mono">
            <ShieldAlert className="h-6 w-6 text-amber-400 mx-auto" />
            <div className="text-xs text-foreground font-semibold">No Policies Configured</div>
            <p className="text-[11px] text-muted-foreground max-w-md mx-auto">
              Create a policy rule set to govern deployment risk evaluations, approval gates, and incident containment.
            </p>
          </div>
        ) : (
          policies.map((p) => (
            <div
              key={p.id}
              className={`p-5 rounded-lg border bg-card space-y-4 font-mono text-xs transition-colors ${
                p.enabled ? "border-emerald-500/40 bg-emerald-950/5" : "border-border opacity-70"
              }`}
            >
              <div className="flex items-center justify-between pb-3 border-b border-border">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-foreground font-bold text-sm">{p.name}</span>
                    <span className="px-2 py-0.5 rounded text-[10px] bg-muted text-muted-foreground border border-border">
                      v{p.policy_version || "1.0.0"}
                    </span>
                    {p.enabled ? (
                      <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-semibold">
                        ACTIVE EVALUATOR
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded text-[10px] bg-zinc-500/10 text-zinc-400 border border-zinc-500/30">
                        DISABLED
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    {p.description || "No description provided."}
                  </div>
                </div>

                <button
                  onClick={() => handleToggle(p)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-semibold border transition-colors ${
                    p.enabled
                      ? "bg-rose-500/10 border-rose-500/30 text-rose-400 hover:bg-rose-500/20"
                      : "bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20"
                  }`}
                >
                  {p.enabled ? (
                    <>
                      <ToggleRight className="h-4 w-4" />
                      Deactivate
                    </>
                  ) : (
                    <>
                      <ToggleLeft className="h-4 w-4" />
                      Activate
                    </>
                  )}
                </button>
              </div>

              {/* Threshold Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[11px]">
                <div className="p-2.5 rounded bg-background/60 border border-border space-y-0.5">
                  <div className="text-muted-foreground text-[10px] uppercase">Max Risk Threshold</div>
                  <div className="font-bold text-foreground">
                    {p.policy_definition?.max_risk_score !== undefined
                      ? (p.policy_definition.max_risk_score * 100).toFixed(0) + "%"
                      : "0.65"}
                  </div>
                </div>
                <div className="p-2.5 rounded bg-background/60 border border-border space-y-0.5">
                  <div className="text-muted-foreground text-[10px] uppercase">Max Impact Score</div>
                  <div className="font-bold text-foreground">
                    {p.policy_definition?.max_impact_score !== undefined
                      ? (p.policy_definition.max_impact_score * 100).toFixed(0) + "%"
                      : "0.70"}
                  </div>
                </div>
                <div className="p-2.5 rounded bg-background/60 border border-border space-y-0.5">
                  <div className="text-muted-foreground text-[10px] uppercase">Active P1 Block</div>
                  <div className="font-bold text-rose-400">
                    {p.policy_definition?.block_on_p1_incidents ? "ENFORCED" : "OFF"}
                  </div>
                </div>
                <div className="p-2.5 rounded bg-background/60 border border-border space-y-0.5">
                  <div className="text-muted-foreground text-[10px] uppercase">Max Blast Radius</div>
                  <div className="font-bold text-foreground">
                    {p.policy_definition?.max_allowed_blast_radius ?? 5} downstream services
                  </div>
                </div>
              </div>

              {/* Environment Gates */}
              <div className="flex items-center gap-2 pt-1 text-[11px]">
                <span className="text-muted-foreground">Enforced Environments:</span>
                <div className="flex items-center gap-1.5 flex-wrap">
                  {(p.policy_definition?.require_approval_environments || ["production"]).map((env: string) => (
                    <span
                      key={env}
                      className="px-2 py-0.5 rounded bg-background border border-border text-foreground font-semibold text-[10px]"
                    >
                      {env}
                    </span>
                  ))}
                </div>
              </div>

              <div className="text-[10px] text-muted-foreground/60 flex items-center justify-between pt-1 border-t border-border/40">
                <span>Policy ID: {p.id}</span>
                <span>Created {formatDate(p.created_at)}</span>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-card border border-border rounded-xl shadow-2xl max-w-lg w-full p-6 space-y-5 font-mono text-xs">
            <div className="flex items-center justify-between pb-3 border-b border-border">
              <div className="flex items-center gap-2">
                <FileCheck className="h-4 w-4 text-emerald-400" />
                <span className="font-bold text-sm text-foreground">Create Deployment Policy</span>
              </div>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                <XCircle className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleCreatePolicy} className="space-y-4">
              <div className="space-y-1">
                <label className="text-[10px] uppercase text-muted-foreground font-semibold">
                  Policy Name
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Production Zero-Trust Deployment Gate"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="w-full p-2 rounded bg-background border border-border text-foreground text-xs focus:outline-none focus:border-accent"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[10px] uppercase text-muted-foreground font-semibold">
                    Policy Version
                  </label>
                  <input
                    type="text"
                    value={formVersion}
                    onChange={(e) => setFormVersion(e.target.value)}
                    className="w-full p-2 rounded bg-background border border-border text-foreground text-xs focus:outline-none focus:border-accent"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] uppercase text-muted-foreground font-semibold">
                    Max Blast Radius (Services)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="20"
                    value={maxBlastRadius}
                    onChange={(e) => setMaxBlastRadius(Number(e.target.value))}
                    className="w-full p-2 rounded bg-background border border-border text-foreground text-xs focus:outline-none focus:border-accent"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[10px] uppercase text-muted-foreground font-semibold">
                    Max Risk Score (0.0 - 1.0)
                  </label>
                  <input
                    type="number"
                    step="0.05"
                    min="0"
                    max="1"
                    value={maxRiskScore}
                    onChange={(e) => setMaxRiskScore(Number(e.target.value))}
                    className="w-full p-2 rounded bg-background border border-border text-foreground text-xs focus:outline-none focus:border-accent"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] uppercase text-muted-foreground font-semibold">
                    Max Impact Score (0.0 - 1.0)
                  </label>
                  <input
                    type="number"
                    step="0.05"
                    min="0"
                    max="1"
                    value={maxImpactScore}
                    onChange={(e) => setMaxImpactScore(Number(e.target.value))}
                    className="w-full p-2 rounded bg-background border border-border text-foreground text-xs focus:outline-none focus:border-accent"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] uppercase text-muted-foreground font-semibold">
                  Require Approval Environments (comma separated)
                </label>
                <input
                  type="text"
                  value={environments}
                  onChange={(e) => setEnvironments(e.target.value)}
                  className="w-full p-2 rounded bg-background border border-border text-foreground text-xs focus:outline-none focus:border-accent"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[10px] uppercase text-muted-foreground font-semibold">
                  Description
                </label>
                <textarea
                  rows={2}
                  placeholder="Enforces strict human approval and blocks releases when active P1 incidents exist."
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  className="w-full p-2 rounded bg-background border border-border text-foreground text-xs focus:outline-none focus:border-accent"
                />
              </div>

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="blockP1"
                  checked={blockOnP1}
                  onChange={(e) => setBlockOnP1(e.target.checked)}
                  className="rounded border-border text-accent focus:ring-accent"
                />
                <label htmlFor="blockP1" className="text-xs text-foreground cursor-pointer font-semibold">
                  Block deployment if active P1 incident is unresolved
                </label>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-border">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3.5 py-1.5 rounded border border-border text-muted-foreground hover:text-foreground text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-1.5 rounded bg-emerald-500 text-slate-950 font-bold hover:bg-emerald-400 transition-colors disabled:opacity-50 text-xs"
                >
                  {saving ? "Creating..." : "Save & Activate Policy"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
