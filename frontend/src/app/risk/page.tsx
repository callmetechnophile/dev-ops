"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  Flame,
  Layers,
  Cpu,
  ArrowRight,
  ExternalLink,
  RefreshCw,
  Search,
  CheckCircle2,
  Clock,
} from "lucide-react";
import { fetchRiskAssessments, fetchModelStatus, fetchDeployments, triggerRiskAssessment } from "@/lib/api";
import { RiskMeter } from "@/components/risk-meter";
import { StatusBadge } from "@/components/status-badge";
import { formatDate } from "@/lib/utils";

export default function RiskCenterPage() {
  const [assessments, setAssessments] = useState<any[]>([]);
  const [modelStatus, setModelStatus] = useState<any | null>(null);
  const [deployments, setDeployments] = useState<any[]>([]);
  const [selectedDeployId, setSelectedDeployId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  async function loadData() {
    try {
      setLoading(true);
      const [riskRes, modelRes, depRes] = await Promise.all([
        fetchRiskAssessments(),
        fetchModelStatus(),
        fetchDeployments(),
      ]);
      setAssessments(riskRes?.items || []);
      setModelStatus(modelRes);
      setDeployments(depRes?.items || []);
      if (depRes?.items?.length > 0) {
        setSelectedDeployId(depRes.items[0].id);
      }
    } catch (err) {
      console.error("Failed to load risk center:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  const handleTriggerAssessment = async () => {
    if (!selectedDeployId) return;
    setEvaluating(true);
    try {
      await triggerRiskAssessment(selectedDeployId);
      await loadData();
    } catch (err: any) {
      alert(err.message || "Risk assessment failed");
    } finally {
      setEvaluating(false);
    }
  };

  const filteredAssessments = assessments.filter((a) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      a.id.toLowerCase().includes(q) ||
      a.deployment_id.toLowerCase().includes(q) ||
      a.environment.toLowerCase().includes(q) ||
      a.risk_level.toLowerCase().includes(q)
    );
  });

  const lowCount = assessments.filter((a) => a.risk_level === "LOW").length;
  const medCount = assessments.filter((a) => a.risk_level === "MEDIUM").length;
  const highCount = assessments.filter((a) => a.risk_level === "HIGH").length;
  const critCount = assessments.filter((a) => a.risk_level === "CRITICAL").length;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-400" />
            Predictive Deployment Risk Center
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Pre-flight failure prediction, deterministic baseline rules, downstream blast radius, and historical incident correlation.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/risk/models"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-border bg-secondary/50 hover:bg-secondary text-foreground text-xs font-mono transition-colors"
          >
            <Cpu className="h-3.5 w-3.5 text-cyan-400" />
            <span>Model Intelligence</span>
          </Link>
          <button
            onClick={loadData}
            className="p-1.5 rounded border border-border bg-secondary/30 hover:bg-secondary text-muted-foreground hover:text-foreground text-xs font-mono transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Model Status & Assessment Trigger Header Banner */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* ML Status Card */}
        <div className="p-4 rounded border border-border bg-card/60 space-y-2">
          <div className="flex items-center justify-between text-xs font-mono text-muted-foreground">
            <span className="font-semibold flex items-center gap-1.5">
              <Cpu className="h-4 w-4 text-cyan-400" />
              ML ENGINE STATUS
            </span>
            <span
              className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase ${
                modelStatus?.status === "ACTIVE"
                  ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                  : "bg-amber-500/20 text-amber-300 border-amber-500/30"
              }`}
            >
              {modelStatus?.status || "INSUFFICIENT_DATA"}
            </span>
          </div>
          <div className="text-xs text-muted-foreground leading-relaxed">
            {modelStatus?.status === "ACTIVE"
              ? "Calibrated tabular ML model active for deployment failure probability scoring."
              : "Deterministic Stage A baseline active. ML training unlocks when real verified deployment threshold (30 samples) is reached."}
          </div>
          <div className="text-[11px] font-mono text-muted-foreground pt-1">
            Labeled Corpus: {modelStatus?.total_labeled_samples || 0} / {modelStatus?.minimum_required_samples || 30}
          </div>
        </div>

        {/* Risk Distribution Card */}
        <div className="p-4 rounded border border-border bg-card/60 space-y-2">
          <div className="text-xs font-mono text-muted-foreground font-semibold flex items-center justify-between">
            <span>RISK DISTRIBUTION</span>
            <Layers className="h-4 w-4" />
          </div>
          <div className="grid grid-cols-4 gap-1 text-center font-mono">
            <div className="p-1.5 rounded bg-emerald-500/10 border border-emerald-500/20">
              <div className="text-xs font-bold text-emerald-400">{lowCount}</div>
              <div className="text-[9px] text-muted-foreground">LOW</div>
            </div>
            <div className="p-1.5 rounded bg-blue-500/10 border border-blue-500/20">
              <div className="text-xs font-bold text-blue-400">{medCount}</div>
              <div className="text-[9px] text-muted-foreground">MED</div>
            </div>
            <div className="p-1.5 rounded bg-amber-500/10 border border-amber-500/20">
              <div className="text-xs font-bold text-amber-400">{highCount}</div>
              <div className="text-[9px] text-muted-foreground">HIGH</div>
            </div>
            <div className="p-1.5 rounded bg-rose-500/10 border border-rose-500/20">
              <div className="text-xs font-bold text-rose-400">{critCount}</div>
              <div className="text-[9px] text-muted-foreground">CRIT</div>
            </div>
          </div>
          <div className="text-[11px] text-muted-foreground">Total Evaluated: {assessments.length}</div>
        </div>

        {/* Trigger Pre-Flight Assessment Card */}
        <div className="p-4 rounded border border-border bg-card/60 space-y-2">
          <div className="text-xs font-mono text-muted-foreground font-semibold">EVALUATE DEPLOYMENT</div>
          <div className="flex gap-2">
            <select
              value={selectedDeployId}
              onChange={(e) => setSelectedDeployId(e.target.value)}
              className="w-full bg-secondary/60 border border-border text-xs font-mono rounded px-2.5 py-1.5 text-foreground focus:outline-none"
            >
              {deployments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.environment.toUpperCase()} — {d.commit_sha.slice(0, 7)} ({d.status})
                </option>
              ))}
            </select>
            <button
              onClick={handleTriggerAssessment}
              disabled={evaluating || !selectedDeployId}
              className="px-3 py-1.5 rounded bg-amber-500 hover:bg-amber-600 text-black font-mono text-xs font-bold transition-colors disabled:opacity-50 shrink-0"
            >
              {evaluating ? "Evaluating..." : "Run Risk Check"}
            </button>
          </div>
          <div className="text-[11px] text-muted-foreground">
            Extracts pre-flight change features, runs rule baseline, and evaluates blast radius.
          </div>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="flex items-center gap-2 p-3 rounded border border-border bg-card/40">
        <Search className="h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Filter by assessment ID, deployment ID, or environment..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full bg-transparent text-xs font-mono focus:outline-none placeholder:text-muted-foreground"
        />
      </div>

      {/* Risk Assessments Table */}
      <div className="border border-border rounded overflow-hidden bg-card/60">
        <div className="p-3 bg-secondary/30 border-b border-border text-xs font-mono uppercase text-muted-foreground font-semibold flex items-center justify-between">
          <span>Deployment Risk Assessments ({filteredAssessments.length})</span>
          <span>Provenance: Deterministic & ML</span>
        </div>

        {loading ? (
          <div className="p-12 text-center text-xs font-mono text-muted-foreground">
            Loading deployment risk assessments...
          </div>
        ) : filteredAssessments.length === 0 ? (
          <div className="p-16 text-center space-y-2 border-dashed">
            <ShieldCheck className="h-8 w-8 text-muted-foreground mx-auto opacity-40" />
            <div className="text-xs font-mono text-foreground font-semibold">No Risk Evaluations Yet</div>
            <div className="text-[11px] text-muted-foreground max-w-sm mx-auto">
              Select a deployment above and click "Run Risk Check" to generate an evidence-driven assessment.
            </div>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {filteredAssessments.map((a) => (
              <div
                key={a.id}
                className="p-4 hover:bg-secondary/20 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1.5 flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase border ${
                        a.risk_level === "CRITICAL"
                          ? "bg-rose-500/20 text-rose-300 border-rose-500/30"
                          : a.risk_level === "HIGH"
                          ? "bg-amber-500/20 text-amber-300 border-amber-500/30"
                          : a.risk_level === "MEDIUM"
                          ? "bg-blue-500/20 text-blue-300 border-blue-500/30"
                          : "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                      }`}
                    >
                      {a.risk_level} RISK
                    </span>

                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-secondary text-secondary-foreground uppercase">
                      {a.environment}
                    </span>

                    <span className="text-[10px] font-mono text-muted-foreground border border-border px-1.5 py-0.5 rounded">
                      Deployment: {a.deployment_id.slice(0, 8)}...
                    </span>

                    {a.model_version ? (
                      <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/30 border border-cyan-500/30 px-1.5 py-0.5 rounded">
                        ML Model: {a.model_version}
                      </span>
                    ) : (
                      <span className="text-[10px] font-mono text-muted-foreground bg-secondary/50 border border-border px-1.5 py-0.5 rounded">
                        Baseline Rules (v1.0)
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-4 text-xs font-mono pt-1">
                    <span className="text-foreground font-semibold">
                      Overall Score: <span className="text-amber-400">{Math.round(a.overall_risk_score * 100)}%</span>
                    </span>
                    <span className="text-muted-foreground">
                      Rule Baseline: {Math.round(a.rule_score * 100)}%
                    </span>
                    <span className="text-muted-foreground">
                      Blast Radius Impact: {Math.round(a.operational_impact_score * 100)}% ({a.impact_category})
                    </span>
                    {a.failure_probability !== null && a.failure_probability !== undefined && (
                      <span className="text-cyan-400 font-semibold">
                        Calibrated Failure Prob: {Math.round(a.failure_probability * 100)}%
                      </span>
                    )}
                  </div>

                  {a.triggered_rules && a.triggered_rules.length > 0 && (
                    <div className="flex items-center gap-1.5 text-[11px] font-mono text-muted-foreground pt-1 flex-wrap">
                      <span className="font-semibold text-foreground">Triggered Rules:</span>
                      {a.triggered_rules.map((tr: any) => (
                        <span key={tr.rule_id} className="px-1.5 py-0.2 rounded bg-secondary/60 border border-border/60">
                          {tr.title}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="text-[10px] font-mono text-muted-foreground pt-1">
                    Evaluated: {formatDate(a.assessed_at)}
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <Link
                    href={`/risk/${a.id}`}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-medium rounded border border-border bg-secondary/50 hover:bg-secondary text-foreground transition-colors"
                  >
                    <span>Inspect Evidence</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
