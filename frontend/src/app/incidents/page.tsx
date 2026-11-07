"use client";

import React, { useEffect, useState } from "react";
import { Activity, AlertCircle, CheckCircle2, ChevronRight, FileCode } from "lucide-react";
import { fetchIncidents } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { formatDate } from "@/lib/utils";

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<any[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetchIncidents();
        const items = res.items || [];
        setIncidents(items);
        if (items.length > 0) setSelectedIncident(items[0]);
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
          <Activity className="h-5 w-5 text-rose-400" />
          Incident Intelligence & Failure Memory
        </h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Episodic incident records, CrashLoopBackOff/OOM failure classifications, and confirmed root-cause engineering lessons.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Incident List */}
        <div className="space-y-3">
          <div className="text-xs font-mono uppercase text-muted-foreground font-semibold px-1">
            Historical Incidents ({incidents.length})
          </div>

          {incidents.length === 0 ? (
            <div className="p-8 text-center border border-dashed border-border rounded text-xs text-muted-foreground font-mono">
              No incidents recorded in operational memory.
            </div>
          ) : (
            <div className="space-y-2">
              {incidents.map((inc) => (
                <button
                  key={inc.id}
                  onClick={() => setSelectedIncident(inc)}
                  className={`w-full text-left p-3 rounded border text-xs font-mono transition-all ${
                    selectedIncident?.id === inc.id
                      ? "border-rose-500 bg-rose-500/10 shadow-sm"
                      : "border-border bg-card/60 hover:border-border/80"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-foreground truncate">{inc.title}</span>
                    <StatusBadge status={inc.severity} />
                  </div>
                  <div className="mt-1 text-[11px] text-muted-foreground truncate">
                    {inc.summary}
                  </div>
                  <div className="mt-1.5 flex items-center justify-between text-[10px] text-muted-foreground">
                    <span>{formatDate(inc.detected_at)}</span>
                    <StatusBadge status={inc.status} />
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Selected Incident Detail */}
        <div className="lg:col-span-2 space-y-4">
          {selectedIncident ? (
            <div className="p-5 rounded-lg bg-card border border-border space-y-5">
              <div className="flex items-start justify-between pb-4 border-b border-border">
                <div>
                  <div className="text-xs font-mono text-muted-foreground uppercase">
                    Incident ID: {selectedIncident.id}
                  </div>
                  <h2 className="text-base font-bold text-foreground mt-0.5">
                    {selectedIncident.title}
                  </h2>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={selectedIncident.severity} />
                  <StatusBadge status={selectedIncident.status} />
                </div>
              </div>

              <div className="text-xs text-muted-foreground font-mono bg-background/50 p-3 rounded border border-border">
                <span className="text-[10px] uppercase text-muted-foreground font-semibold block mb-1">
                  Incident Summary
                </span>
                {selectedIncident.summary}
              </div>

              {/* Failures Breakdown */}
              <div className="space-y-3 font-mono text-xs">
                <div className="text-xs uppercase font-semibold text-foreground">
                  Detected Failure Signatures ({selectedIncident.failures?.length || 0})
                </div>

                {selectedIncident.failures?.map((f: any) => (
                  <div key={f.id} className="p-3 rounded bg-background/60 border border-border space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-rose-400">{f.failure_type}</span>
                      <span className="text-muted-foreground text-[10px]">
                        Exit Code: {f.exit_code ?? "N/A"}
                      </span>
                    </div>
                    <div className="text-[11px] text-foreground font-mono bg-black/40 p-2 rounded">
                      {f.error_message}
                    </div>
                    {f.pod_name && (
                      <div className="text-[10px] text-muted-foreground">
                        Pod: {f.pod_name} &middot; Container: {f.container_name || "main"}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Confirmed Root Cause */}
              {selectedIncident.confirmed_root_cause ? (
                <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/30 space-y-2 font-mono text-xs">
                  <div className="flex items-center gap-2 font-bold text-emerald-400">
                    <CheckCircle2 className="h-4 w-4" />
                    <span>Confirmed Root Cause & Engineering Lesson</span>
                  </div>
                  <div className="text-foreground">
                    <span className="text-muted-foreground block text-[10px] uppercase">Root Cause:</span>
                    {selectedIncident.confirmed_root_cause.root_cause_summary}
                  </div>
                  <div className="text-foreground">
                    <span className="text-muted-foreground block text-[10px] uppercase">Verified Lesson:</span>
                    {selectedIncident.confirmed_root_cause.verified_engineering_lesson}
                  </div>
                  <div className="text-foreground">
                    <span className="text-muted-foreground block text-[10px] uppercase">Prevention Strategy:</span>
                    {selectedIncident.confirmed_root_cause.prevention_strategy}
                  </div>
                </div>
              ) : (
                <div className="p-4 rounded bg-background/40 border border-dashed border-border text-xs text-muted-foreground font-mono">
                  No confirmed root cause recorded yet. Pending human post-mortem verification.
                </div>
              )}
            </div>
          ) : (
            <div className="p-12 text-center border border-dashed border-border rounded text-xs text-muted-foreground font-mono">
              Select an incident to view root causes and failure signatures.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
