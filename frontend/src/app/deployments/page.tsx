"use client";

import React, { useEffect, useState } from "react";
import { 
  Rocket, 
  ShieldAlert, 
  GitCommit, 
  Clock, 
  CheckCircle2, 
  AlertOctagon, 
  GitPullRequest, 
  PlayCircle, 
  User, 
  CheckCheck,
  Calendar
} from "lucide-react";
import { fetchDeployments, fetchDeploymentRisk, fetchDeploymentTimeline } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { RiskMeter } from "@/components/risk-meter";
import { formatDate } from "@/lib/utils";

export default function DeploymentsPage() {
  const [deployments, setDeployments] = useState<any[]>([]);
  const [selectedDeployment, setSelectedDeployment] = useState<any | null>(null);
  const [timelineData, setTimelineData] = useState<any | null>(null);
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
    async function loadDetails() {
      try {
        const [r, tl] = await Promise.allSettled([
          fetchDeploymentRisk(selectedDeployment.id),
          fetchDeploymentTimeline(selectedDeployment.id)
        ]);
        if (r.status === "fulfilled") setRiskData(r.value);
        if (tl.status === "fulfilled") setTimelineData(tl.value);
      } catch {
        setRiskData(null);
        setTimelineData(null);
      }
    }
    loadDetails();
  }, [selectedDeployment]);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <Rocket className="h-5 w-5 text-sky-400" />
          Deployment History & Provenance
        </h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Deterministic lifecycle tracking from commit, pull request, and CI workflow run to deployment events.
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
              No deployments recorded. Connect GitHub webhooks to capture deployment events.
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
                    SHA: {d.commit_sha.slice(0, 8)}... {d.creator_login ? `(@${d.creator_login})` : ""}
                  </div>
                  <div className="mt-1 text-[10px] text-muted-foreground">
                    {formatDate(d.created_at)}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Selected Deployment Detail & Timeline */}
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
                  <span className="text-muted-foreground block text-[10px] uppercase">Creator</span>
                  <span className="text-foreground">{selectedDeployment.creator_login ? `@${selectedDeployment.creator_login}` : selectedDeployment.triggered_by}</span>
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
                    {selectedDeployment.duration_seconds ? `${selectedDeployment.duration_seconds.toFixed(1)}s` : "Pending"}
                  </span>
                </div>
              </div>

              {/* Timeline Section (Section 9.D) */}
              <div className="pt-4 border-t border-border space-y-3 font-mono">
                <div className="text-xs uppercase font-semibold text-foreground flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-accent" />
                  Chronological Deployment Timeline
                </div>

                {timelineData && timelineData.timeline && timelineData.timeline.length > 0 ? (
                  <div className="relative pl-6 space-y-4 border-l-2 border-border ml-2 my-2">
                    {timelineData.timeline.map((step: any, idx: number) => {
                      let icon = <GitCommit className="h-3.5 w-3.5 text-sky-400" />;
                      if (step.step_type === "pr_merged") icon = <GitPullRequest className="h-3.5 w-3.5 text-purple-400" />;
                      if (step.step_type === "workflow_run") icon = <PlayCircle className="h-3.5 w-3.5 text-accent" />;
                      if (step.step_type === "approval") icon = <CheckCheck className="h-3.5 w-3.5 text-emerald-400" />;
                      if (step.step_type === "deployment_event") icon = <Rocket className="h-3.5 w-3.5 text-amber-400" />;

                      return (
                        <div key={idx} className="relative group">
                          <div className="absolute -left-[31px] top-0 p-1 rounded-full bg-card border border-border">
                            {icon}
                          </div>
                          <div className="p-3 rounded bg-background/50 border border-border text-xs space-y-1">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-foreground">{step.title}</span>
                              <span className="text-[10px] text-muted-foreground">{formatDate(step.timestamp)}</span>
                            </div>
                            {step.description && (
                              <div className="text-[11px] text-muted-foreground">
                                {step.description}
                              </div>
                            )}
                            {step.actor && (
                              <div className="text-[10px] text-muted-foreground">
                                Actor: @{step.actor}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="p-6 text-center border border-dashed border-border rounded text-xs text-muted-foreground font-mono">
                    Awaiting correlation events for this deployment cycle.
                  </div>
                )}
              </div>

              {/* Associated Risk Intelligence */}
              <div className="pt-4 border-t border-border space-y-3">
                <div className="text-xs font-mono uppercase font-semibold text-foreground flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4 text-amber-400" />
                  Pre-Deployment Risk Intelligence
                </div>

                {riskData ? (
                  <div className="p-4 rounded border border-border bg-background/50 space-y-4 font-mono text-xs">
                    <RiskMeter score={riskData.overall_risk_score} label="Overall Risk Assessment" />
                  </div>
                ) : (
                  <div className="p-4 text-center border border-dashed border-border rounded text-xs text-muted-foreground font-mono">
                    No risk assessment generated yet for this deployment cycle.
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="p-12 text-center border border-dashed border-border rounded text-xs text-muted-foreground font-mono">
              Select a deployment from the left panel to inspect details and timeline.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
