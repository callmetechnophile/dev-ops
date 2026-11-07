"use client";

import React, { useEffect, useState } from "react";
import { AlertTriangle, ShieldCheck, CheckCircle2, FileText, ArrowRight } from "lucide-react";
import { fetchDeployments, fetchDeploymentRisk } from "@/lib/api";
import { RiskMeter } from "@/components/risk-meter";
import { StatusBadge } from "@/components/status-badge";
import Link from "next/link";

export default function RiskCenterPage() {
  const [assessments, setAssessments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const depRes = await fetchDeployments();
        const items = depRes.items || [];
        const riskPromises = items.map(async (d: any) => {
          const risk = await fetchDeploymentRisk(d.id).catch(() => null);
          return risk ? { ...risk, deployment: d } : null;
        });
        const resolved = await Promise.all(riskPromises);
        setAssessments(resolved.filter(Boolean));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-400" />
          Pre-Deployment Risk Assessment Center
        </h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Deterministic heuristics (Stage A) & Machine Learning predictions (Stage B).
        </p>
      </div>

      {assessments.length === 0 ? (
        <div className="p-12 text-center border border-dashed border-border rounded-lg bg-card/40 space-y-3 font-mono">
          <ShieldCheck className="h-8 w-8 text-muted-foreground mx-auto" />
          <div className="text-sm text-foreground font-semibold">No Risk Evaluations Yet</div>
          <p className="text-xs text-muted-foreground max-w-md mx-auto">
            Risk evaluations trigger automatically when deployment events arrive from GitHub Actions or CI pipeline triggers.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {assessments.map((a) => (
            <div key={a.id} className="p-4 rounded-lg bg-card border border-border space-y-4 font-mono">
              <div className="flex items-center justify-between pb-2 border-b border-border">
                <span className="text-xs font-semibold text-foreground">
                  Deployment {a.deployment_id.slice(0, 8)}...
                </span>
                <StatusBadge status={a.risk_level} />
              </div>

              <RiskMeter score={a.overall_risk_score} label="Overall Composite Risk" />

              <div className="grid grid-cols-2 gap-2 text-[11px] text-muted-foreground">
                <div>
                  <span>Rule Engine Score: </span>
                  <span className="text-foreground font-bold">{a.rule_score.toFixed(2)}</span>
                </div>
                <div>
                  <span>Failure Probability: </span>
                  <span className="text-foreground font-bold">
                    {a.failure_probability !== null ? `${(a.failure_probability * 100).toFixed(0)}%` : "Stage A"}
                  </span>
                </div>
              </div>

              {a.triggered_rules && a.triggered_rules.length > 0 && (
                <div className="p-2.5 rounded bg-background/50 border border-border space-y-1">
                  <div className="text-[10px] uppercase text-muted-foreground font-semibold">
                    Triggered Risk Rules ({a.triggered_rules.length})
                  </div>
                  {a.triggered_rules.map((r: any, idx: number) => (
                    <div key={idx} className="text-[11px] text-amber-300">
                      &bull; {r.rule_name || r.rule_id}: {r.description}
                    </div>
                  ))}
                </div>
              )}

              <Link
                href={`/deployments`}
                className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
              >
                Inspect Full Evidence <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
