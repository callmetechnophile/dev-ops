"use client";

import React, { useEffect, useState } from "react";
import { Rocket, ShieldAlert, GitCommit, Clock, CheckCircle2, AlertOctagon } from "lucide-react";
import { fetchDeployments, fetchDeploymentRisk } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { RiskMeter } from "@/components/risk-meter";
import { formatDate } from "@/lib/utils";

export default function DeploymentsPage() {
  const [deployments, setDeployments] = useState<any[]>([]);
  const [selectedDeployment, setSelectedDeployment] = useState<any | null>(null);
  const [riskData, setRiskData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetchDeployments();
        const items = res.items || [];
        setDeployments(items);
        if (items.length > 0) {
          setSelectedDeployment(items[0]);
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  useEffect(() => {
    if (!selectedDeployment) return;
    async function loadRisk() {
      try {
        const r = await fetchDeploymentRisk(selectedDeployment.id);
        setRiskData(r);
      } catch {
        setRiskData(null);
      }
    }
    loadRisk();
  }, [selectedDeployment]);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <Rocket className="h-5 w-5 text-sky-400" />
          Deployment History & Provenance
        </h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Immutable ledger of CI/CD triggers, state transitions, and associated operational risk evaluations.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Deployments List */}
        <div className="lg:col-span-1 space-y-3">
          <div className="text-xs font-mono uppercase text-muted-foreground font-semibold px-1">
            Recorded Cycles ({deployments.length})
          </div>

          {deployments.length === 0 ? (
            <div className="p-8 text-center border border-dashed border-border rounded text-xs text-muted-foreground font-mono">
              No deployments recorded.
            </div>
          ) : (
            <div className="space-y-2">
              {deployments.map((d) => (
                <button
                  key={d.id}
                  onClick={() => setSelectedDeployment(d)}
                  className={`w-full text-left p-3 rounded border text-xs font-mono transition-all ${
                    selectedDeployment?.id === d.id
                      ? "border-accent bg-accent/10 shadow-sm"
                      : "border-border bg-card/60 hover:border-border/80"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-foreground uppercase">{d.environment}</span>
                    <StatusBadge status={d.status} />
                  </div>
                  <div className="mt-1 text-[11px] text-muted-foreground truncate">
                    SHA: {d.commit_sha.slice(0, 8)}...
                  </div>
                  <div className="mt-1 text-[10px] text-muted-foreground">
                    {formatDate(d.created_at)}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Selected Deployment Detail & Risk Inspector */}
        <div className="lg:col-span-2 space-y-4">
          {selectedDeployment ? (
            <div className="p-5 rounded-lg bg-card border border-border space-y-5">
              <div className="flex items-start justify-between pb-4 border-b border-border">
                <div>
                  <div className="text-xs font-mono text-muted-foreground uppercase">
                    Deployment ID
                  </div>
                  <div className="text-sm font-mono font-bold text-foreground">
                    {selectedDeployment.id}
                  </div>
                </div>
                <StatusBadge status={selectedDeployment.status} />
              </div>

              {/* Metadata attributes */}
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-xs font-mono">
                <div>
                  <span className="text-muted-foreground block text-[10px] uppercase">Service ID</span>
                  <span className="text-foreground">{selectedDeployment.service_id.slice(0, 13)}...</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px] uppercase">Environment</span>
                  <span className="text-foreground font-semibold">{selectedDeployment.environment}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px] uppercase">Triggered By</span>
                  <span className="text-foreground">{selectedDeployment.triggered_by}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px] uppercase">Commit SHA</span>
                  <span className="text-foreground font-mono">{selectedDeployment.commit_sha}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px] uppercase">Started At</span>
                  <span className="text-foreground">{formatDate(selectedDeployment.started_at)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px] uppercase">Duration</span>
                  <span className="text-foreground">
                    {selectedDeployment.duration_seconds ? `${selectedDeployment.duration_seconds}s` : "Pending"}
                  </span>
                </div>
              </div>

              {/* Associated Risk Intelligence */}
              <div className="pt-4 border-t border-border space-y-3">
                <div className="text-xs font-mono uppercase font-semibold text-foreground flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4 text-amber-400" />
                  Pre-Deployment Risk Intelligence
                </div>

                {riskData ? (
                  <div className="p-4 rounded border border-border bg-background/50 space-y-4 font-mono text-xs">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <RiskMeter score={riskData.overall_risk_score} label="Overall Risk Assessment" />
                      <div className="space-y-1">
                        <span className="text-muted-foreground block text-[10px] uppercase">Failure Probability</span>
                        <span className="text-foreground font-bold">
                          {riskData.failure_probability !== null
                            ? `${(riskData.failure_probability * 100).toFixed(1)}% (Calibrated)`
                            : "Heuristic Stage A (Deterministic)"}
                        </span>
                      </div>
                    </div>

                    {/* Triggered Rules */}
                    {riskData.triggered_rules && riskData.triggered_rules.length > 0 && (
                      <div className="space-y-2">
                        <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                          Triggered Operational Rules
                        </span>
                        {riskData.triggered_rules.map((rule: any, idx: number) => (
                          <div key={idx} className="p-2.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-300">
                            <div className="font-bold flex items-center justify-between">
                              <span>{rule.rule_id}</span>
                              <span className="text-[10px] uppercase">{rule.severity}</span>
                            </div>
                            <div className="text-[11px] text-amber-200/80 mt-1">
                              {rule.description}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Recommendations */}
                    {riskData.recommendations && riskData.recommendations.length > 0 && (
                      <div className="space-y-2">
                        <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                          Agent Recommendations
                        </span>
                        {riskData.recommendations.map((rec: any) => (
                          <div key={rec.id} className="p-3 rounded bg-card border border-border space-y-1">
                            <div className="font-bold text-accent">{rec.title}</div>
                            <div className="text-muted-foreground text-[11px]">{rec.rationale}</div>
                            {rec.mitigation_steps && (
                              <ul className="list-disc pl-4 text-[11px] text-muted-foreground pt-1 space-y-0.5">
                                {rec.mitigation_steps.map((step: string, i: number) => (
                                  <li key={i}>{step}</li>
                                ))}
                              </ul>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-6 text-center border border-dashed border-border rounded text-xs text-muted-foreground font-mono">
                    No risk assessment generated yet for this deployment cycle.
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="p-12 text-center border border-dashed border-border rounded text-xs text-muted-foreground font-mono">
              Select a deployment from the left panel to inspect details.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
