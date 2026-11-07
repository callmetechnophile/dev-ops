"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ExternalLink,
  Flame,
  Layers,
  Search,
  ShieldAlert,
  Terminal,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { fetchIncidents, fetchIncidentAnalytics } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { formatDate } from "@/lib/utils";

export default function IncidentsDashboard() {
  const [incidents, setIncidents] = useState<any[]>([]);
  const [analytics, setAnalytics] = useState<any | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>("ALL");
  const [filterSeverity, setFilterSeverity] = useState<string>("ALL");
  const [filterCategory, setFilterCategory] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [incRes, anaRes] = await Promise.all([
          fetchIncidents(),
          fetchIncidentAnalytics(),
        ]);
        setIncidents(incRes?.items || []);
        setAnalytics(anaRes);
      } catch (e) {
        console.error("Failed to load incidents:", e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const filteredIncidents = incidents.filter((inc) => {
    if (filterStatus !== "ALL" && inc.status !== filterStatus) return false;
    if (filterSeverity !== "ALL" && inc.severity !== filterSeverity) return false;
    if (filterCategory !== "ALL" && inc.incident_type !== filterCategory) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchKey = inc.incident_key?.toLowerCase().includes(q);
      const matchTitle = inc.title?.toLowerCase().includes(q);
      const matchSummary = inc.summary?.toLowerCase().includes(q);
      if (!matchKey && !matchTitle && !matchSummary) return false;
    }
    return true;
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Activity className="h-5 w-5 text-rose-500" />
            Incident Intelligence & Failure Memory
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Operational failure detection, deterministic classification, chronological reconstruction, and verified engineering lessons.
          </p>
        </div>
      </div>

      {/* Analytics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded border border-border bg-card/60 backdrop-blur-sm">
          <div className="flex items-center justify-between text-muted-foreground text-xs font-mono">
            <span>TOTAL INCIDENTS</span>
            <Layers className="h-4 w-4" />
          </div>
          <div className="text-2xl font-bold font-mono mt-2 text-foreground">
            {analytics?.total_incidents ?? incidents.length}
          </div>
          <div className="text-[11px] text-muted-foreground mt-1">Recorded operational anomalies</div>
        </div>

        <div className="p-4 rounded border border-rose-950/60 bg-rose-500/5 backdrop-blur-sm">
          <div className="flex items-center justify-between text-rose-400 text-xs font-mono">
            <span>OPEN INCIDENTS</span>
            <ShieldAlert className="h-4 w-4" />
          </div>
          <div className="text-2xl font-bold font-mono mt-2 text-rose-400">
            {analytics?.open_incidents ?? incidents.filter((i) => i.status === "OPEN").length}
          </div>
          <div className="text-[11px] text-muted-foreground mt-1">Awaiting verification or resolution</div>
        </div>

        <div className="p-4 rounded border border-emerald-950/60 bg-emerald-500/5 backdrop-blur-sm">
          <div className="flex items-center justify-between text-emerald-400 text-xs font-mono">
            <span>RESOLVED & LESSONS</span>
            <CheckCircle2 className="h-4 w-4" />
          </div>
          <div className="text-2xl font-bold font-mono mt-2 text-emerald-400">
            {analytics?.resolved_incidents ?? incidents.filter((i) => i.status === "RESOLVED").length}
          </div>
          <div className="text-[11px] text-muted-foreground mt-1">Confirmed with post-mortem lessons</div>
        </div>

        <div className="p-4 rounded border border-amber-950/60 bg-amber-500/5 backdrop-blur-sm">
          <div className="flex items-center justify-between text-amber-400 text-xs font-mono">
            <span>CRITICAL P1 RATE</span>
            <Flame className="h-4 w-4" />
          </div>
          <div className="text-2xl font-bold font-mono mt-2 text-amber-400">
            {analytics?.p1_count ?? incidents.filter((i) => i.severity === "P1").length}
          </div>
          <div className="text-[11px] text-muted-foreground mt-1">Production impact incidents</div>
        </div>
      </div>

      {/* Category Breakdown & Trend Section */}
      {analytics?.category_distribution && Object.keys(analytics.category_distribution).length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded border border-border bg-card/40">
            <div className="text-xs font-mono text-muted-foreground uppercase font-semibold mb-3 flex items-center gap-1.5">
              <Layers className="h-3.5 w-3.5" />
              Failure Category Distribution
            </div>
            <div className="space-y-2">
              {Object.entries(analytics.category_distribution).map(([cat, count]) => {
                const total = analytics.total_incidents || 1;
                const pct = Math.round(((count as number) / total) * 100);
                return (
                  <div key={cat} className="space-y-1">
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-foreground">{cat}</span>
                      <span className="text-muted-foreground">
                        {count as number} ({pct}%)
                      </span>
                    </div>
                    <div className="h-1.5 w-full bg-secondary rounded-full overflow-hidden">
                      <div
                        className="h-full bg-rose-500/70 rounded-full"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="p-4 rounded border border-border bg-card/40">
            <div className="text-xs font-mono text-muted-foreground uppercase font-semibold mb-3 flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5" />
              Environment Distribution
            </div>
            <div className="space-y-2">
              {analytics.environment_distribution &&
                Object.entries(analytics.environment_distribution).map(([env, count]) => (
                  <div
                    key={env}
                    className="flex items-center justify-between p-2 rounded bg-secondary/30 text-xs font-mono"
                  >
                    <span className="text-foreground font-semibold uppercase">{env}</span>
                    <span className="text-muted-foreground">{count as number} Incident(s)</span>
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}

      {/* Filters and Search Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded border border-border bg-card/40">
        <div className="flex items-center gap-2 flex-1 min-w-[240px]">
          <Search className="h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search by INC-key, summary, or error message..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-transparent text-xs font-mono focus:outline-none placeholder:text-muted-foreground"
          />
        </div>

        <div className="flex items-center gap-2">
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="bg-secondary/60 border border-border text-xs font-mono rounded px-2.5 py-1 text-foreground focus:outline-none"
          >
            <option value="ALL">All Statuses</option>
            <option value="OPEN">Open</option>
            <option value="RESOLVED">Resolved</option>
          </select>

          <select
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value)}
            className="bg-secondary/60 border border-border text-xs font-mono rounded px-2.5 py-1 text-foreground focus:outline-none"
          >
            <option value="ALL">All Severities</option>
            <option value="P1">P1 (Critical)</option>
            <option value="P2">P2 (Major)</option>
            <option value="P3">P3 (Minor)</option>
          </select>

          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            className="bg-secondary/60 border border-border text-xs font-mono rounded px-2.5 py-1 text-foreground focus:outline-none"
          >
            <option value="ALL">All Categories</option>
            <option value="BUILD_FAILURE">BUILD_FAILURE</option>
            <option value="DEPLOYMENT_FAILURE">DEPLOYMENT_FAILURE</option>
            <option value="CONFIGURATION_FAILURE">CONFIGURATION_FAILURE</option>
            <option value="INFRASTRUCTURE_FAILURE">INFRASTRUCTURE_FAILURE</option>
            <option value="UNKNOWN_FAILURE">UNKNOWN_FAILURE</option>
          </select>
        </div>
      </div>

      {/* Incident List Table */}
      <div className="border border-border rounded overflow-hidden bg-card/60">
        <div className="p-3 bg-secondary/30 border-b border-border text-xs font-mono uppercase text-muted-foreground font-semibold flex items-center justify-between">
          <span>Operational Incidents ({filteredIncidents.length})</span>
          <span>Chronological Ingestion Order</span>
        </div>

        {loading ? (
          <div className="p-12 text-center text-xs font-mono text-muted-foreground">
            Loading incident intelligence records...
          </div>
        ) : filteredIncidents.length === 0 ? (
          <div className="p-16 text-center space-y-2">
            <CheckCircle2 className="h-8 w-8 text-muted-foreground mx-auto opacity-40" />
            <div className="text-xs font-mono text-foreground font-semibold">No Incidents Found</div>
            <div className="text-[11px] text-muted-foreground max-w-sm mx-auto">
              No matching failure signals recorded. Real operational incidents will automatically populate when CI/CD or deployment failures are ingested.
            </div>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {filteredIncidents.map((inc) => (
              <div
                key={inc.id}
                className="p-4 hover:bg-secondary/20 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1.5 flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs font-bold text-rose-400 bg-rose-500/10 border border-rose-500/20 px-2 py-0.5 rounded">
                      {inc.incident_key}
                    </span>
                    <span
                      className={`text-[10px] font-mono px-1.5 py-0.5 rounded border uppercase ${
                        inc.severity === "P1"
                          ? "bg-rose-500/20 text-rose-300 border-rose-500/30 font-bold"
                          : "bg-amber-500/20 text-amber-300 border-amber-500/30"
                      }`}
                    >
                      {inc.severity}
                    </span>
                    <StatusBadge status={inc.status} />
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-secondary text-secondary-foreground">
                      {inc.environment}
                    </span>
                    <span className="text-[10px] font-mono text-muted-foreground border border-border/60 px-1.5 py-0.5 rounded">
                      {inc.incident_type}
                    </span>
                  </div>

                  <h3 className="text-sm font-semibold text-foreground truncate">{inc.title}</h3>
                  <p className="text-xs text-muted-foreground line-clamp-1">{inc.summary}</p>

                  <div className="flex items-center gap-4 text-[11px] font-mono text-muted-foreground pt-1">
                    <span>Detected: {formatDate(inc.detected_at)}</span>
                    {inc.resolved_at && (
                      <span className="text-emerald-400">
                        Resolved: {formatDate(inc.resolved_at)}
                      </span>
                    )}
                    {inc.confirmed_root_cause && (
                      <span className="text-cyan-400 font-semibold flex items-center gap-1">
                        ✓ Root Cause Verified
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <Link
                    href={`/incidents/${inc.id}`}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-medium rounded border border-border bg-secondary/50 hover:bg-secondary text-foreground transition-colors"
                  >
                    <span>Inspect Incident</span>
                    <ExternalLink className="h-3 w-3" />
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
