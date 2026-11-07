"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { 
  Rocket, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  Brain, 
  ShieldCheck, 
  ArrowRight,
  Server,
  Layers,
  GitBranch,
  XCircle,
  Activity
} from "lucide-react";
import { 
  fetchHealth, 
  fetchDeployments, 
  fetchIncidents, 
  fetchApprovals, 
  fetchWorkflows,
  fetchGitHubStatus 
} from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { formatDate } from "@/lib/utils";

export default function OverviewPage() {
  const [health, setHealth] = useState<any>(null);
  const [githubStatus, setGithubStatus] = useState<any>(null);
  const [deployments, setDeployments] = useState<any[]>([]);
  const [workflows, setWorkflows] = useState<any[]>([]);
  const [incidents, setIncidents] = useState<any[]>([]);
  const [approvals, setApprovals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [h, gh, d, w, inc, app] = await Promise.allSettled([
          fetchHealth(),
          fetchGitHubStatus(),
          fetchDeployments(),
          fetchWorkflows(),
          fetchIncidents(),
          fetchApprovals(),
        ]);
        if (h.status === "fulfilled") setHealth(h.value);
        if (gh.status === "fulfilled") setGithubStatus(gh.value);
        if (d.status === "fulfilled") setDeployments(d.value.items || []);
        if (w.status === "fulfilled") setWorkflows(w.value.items || []);
        if (inc.status === "fulfilled") setIncidents(inc.value.items || []);
        if (app.status === "fulfilled") setApprovals(app.value.items || []);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const totalDeployments = deployments.length;
  const successfulDeployments = deployments.filter((d) => d.status === "SUCCEEDED").length;
  const failedDeployments = deployments.filter((d) => d.status === "FAILED").length;
  const pendingApprovals = approvals.filter((a) => a.status === "WAITING_FOR_APPROVAL");

  // Calculate deployment frequency (deployments in last 7 days or total if small)
  const successRate = totalDeployments > 0 ? Math.round((successfulDeployments / totalDeployments) * 100) : 0;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Banner / Hero */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between pb-4 border-b border-border gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            DevOps Intelligence Control Center
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Operational memory of past failures &middot; Pre-deployment risk forecasting &middot; Human-gated intervention
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/approvals"
            className="flex items-center gap-2 px-3 py-1.5 rounded text-xs font-mono font-medium bg-amber-500/10 text-amber-400 border border-amber-500/30 hover:bg-amber-500/20 transition-colors"
          >
            <Clock className="h-3.5 w-3.5" />
            <span>Gated Approvals ({pendingApprovals.length})</span>
          </Link>
          <Link
            href="/settings"
            className="flex items-center gap-2 px-3 py-1.5 rounded text-xs font-mono font-medium bg-muted text-muted-foreground border border-border hover:text-foreground transition-colors"
          >
            <Server className="h-3.5 w-3.5" />
            <span>GitHub Connector: {githubStatus?.status || "CHECKING"}</span>
          </Link>
        </div>
      </div>

      {/* Deployment Overview Metrics (Section 9.A) */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-lg bg-card border border-border space-y-2">
          <div className="flex items-center justify-between text-xs font-mono text-muted-foreground">
            <span>Total Deployments</span>
            <Rocket className="h-4 w-4 text-sky-400" />
          </div>
          <div className="text-2xl font-bold text-foreground">
            {totalDeployments}
          </div>
          <div className="text-[11px] text-muted-foreground font-mono flex items-center justify-between">
            <span>Success Rate:</span>
            <span className="text-emerald-400 font-bold">{successRate}%</span>
          </div>
        </div>

        <div className="p-4 rounded-lg bg-card border border-border space-y-2">
          <div className="flex items-center justify-between text-xs font-mono text-muted-foreground">
            <span>Successful / Failed</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-foreground flex items-center gap-2">
            <span className="text-emerald-400">{successfulDeployments}</span>
            <span className="text-muted-foreground text-sm font-normal">/</span>
            <span className="text-rose-400">{failedDeployments}</span>
          </div>
          <div className="text-[11px] text-muted-foreground font-mono">
            {deployments.filter((d) => d.status === "WAITING_FOR_APPROVAL").length} waiting approval
          </div>
        </div>

        <div className="p-4 rounded-lg bg-card border border-border space-y-2">
          <div className="flex items-center justify-between text-xs font-mono text-muted-foreground">
            <span>CI Workflow Runs</span>
            <GitBranch className="h-4 w-4 text-accent" />
          </div>
          <div className="text-2xl font-bold text-foreground">
            {workflows.length}
          </div>
          <div className="text-[11px] text-muted-foreground font-mono">
            Correlated with commits & builds
          </div>
        </div>

        <div className="p-4 rounded-lg bg-card border border-border space-y-2">
          <div className="flex items-center justify-between text-xs font-mono text-muted-foreground">
            <span>Incident Memory</span>
            <AlertTriangle className="h-4 w-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-foreground">
            {incidents.length}
          </div>
          <div className="text-[11px] text-muted-foreground font-mono">
            Episodic memory synchronized
          </div>
        </div>
      </div>

      {/* Main Grid: Pending Approvals & Recent Deployments */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pending Approvals Section */}
        <div className="p-4 rounded-lg bg-card border border-border space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <Clock className="h-4 w-4 text-amber-400" />
              <span>Pending Human Approvals</span>
            </h2>
            <Link
              href="/approvals"
              className="text-xs text-accent hover:underline flex items-center gap-1 font-mono"
            >
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>

          {pendingApprovals.length === 0 ? (
            <div className="p-8 text-center border border-dashed border-border rounded text-xs text-muted-foreground font-mono">
              No pending approval requests. Deployments are either approved or idling.
            </div>
          ) : (
            <div className="space-y-3">
              {pendingApprovals.map((req) => (
                <div
                  key={req.id}
                  className="p-3 rounded border border-amber-500/20 bg-amber-500/5 space-y-2"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-mono font-medium text-amber-300">
                      {req.requested_action}
                    </span>
                    <StatusBadge status={req.status} />
                  </div>
                  <div className="text-[11px] text-muted-foreground font-mono">
                    Deployment: {req.deployment_id.slice(0, 8)}... &middot; Created {formatDate(req.created_at)}
                  </div>
                  <Link
                    href="/approvals"
                    className="inline-block text-xs font-mono text-accent hover:underline"
                  >
                    Review Rationale & Decide &rarr;
                  </Link>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Deployments */}
        <div className="p-4 rounded-lg bg-card border border-border space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <Rocket className="h-4 w-4 text-sky-400" />
              <span>Recent Deployments</span>
            </h2>
            <Link
              href="/deployments"
              className="text-xs text-accent hover:underline flex items-center gap-1 font-mono"
            >
              All history <ArrowRight className="h-3 w-3" />
            </Link>
          </div>

          {deployments.length === 0 ? (
            <div className="p-8 text-center border border-dashed border-border rounded text-xs text-muted-foreground font-mono">
              No deployment cycles recorded. Awaiting GitHub webhook or deployment trigger.
            </div>
          ) : (
            <div className="space-y-2">
              {deployments.slice(0, 5).map((dep) => (
                <div
                  key={dep.id}
                  className="p-2.5 rounded border border-border/80 bg-background/50 flex items-center justify-between text-xs font-mono hover:border-accent/40 transition-colors"
                >
                  <div className="space-y-0.5">
                    <div className="text-foreground font-medium flex items-center gap-2">
                      <span>{dep.environment.toUpperCase()}</span>
                      <span className="text-muted-foreground text-[10px]">
                        sha:{dep.commit_sha.slice(0, 7)}
                      </span>
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      {formatDate(dep.created_at)} &middot; {dep.creator_login ? `by @${dep.creator_login}` : dep.triggered_by}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <StatusBadge status={dep.status} />
                    <Link
                      href={`/deployments`}
                      className="text-accent hover:underline text-[11px]"
                    >
                      Timeline
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Subsystems Health Provenance */}
      <div className="p-4 rounded-lg bg-card border border-border space-y-3">
        <h3 className="text-xs font-semibold text-foreground uppercase tracking-wider font-mono">
          System Connectivity & Health Provenance
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs font-mono">
          <div className="p-3 rounded border border-border bg-background/40 flex items-center justify-between">
            <div className="space-y-0.5">
              <div className="text-foreground">PostgreSQL / pgvector</div>
              <div className="text-[10px] text-muted-foreground">
                Latency: {health?.components?.database?.latency_ms ?? 0} ms
              </div>
            </div>
            <StatusBadge status={health?.components?.database?.status || "UNKNOWN"} />
          </div>

          <div className="p-3 rounded border border-border bg-background/40 flex items-center justify-between">
            <div className="space-y-0.5">
              <div className="text-foreground">Redis Streams Bus</div>
              <div className="text-[10px] text-muted-foreground">
                Latency: {health?.components?.redis?.latency_ms ?? 0} ms
              </div>
            </div>
            <StatusBadge status={health?.components?.redis?.status || "UNKNOWN"} />
          </div>

          <div className="p-3 rounded border border-border bg-background/40 flex items-center justify-between">
            <div className="space-y-0.5">
              <div className="text-foreground">GitHub Webhook Pipeline</div>
              <div className="text-[10px] text-muted-foreground">
                Status: {githubStatus?.status || "PENDING"}
              </div>
            </div>
            <StatusBadge status={githubStatus?.status === "CONFIGURED" ? "ACTIVE" : "PENDING"} />
          </div>
        </div>
      </div>
    </div>
  );
}
