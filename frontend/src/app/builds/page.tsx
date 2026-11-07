"use client";

import React, { useEffect, useState } from "react";
import { Layers, GitBranch, Clock, CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import { fetchBuilds } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { formatDate } from "@/lib/utils";

export default function BuildHistoryPage() {
  const [builds, setBuilds] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetchBuilds();
        setBuilds(res.items || []);
      } catch (err) {
        console.error(err);
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
          <Layers className="h-5 w-5 text-accent" />
          Build Execution & CI History
        </h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Correlated build executions, duration tracking, test outcomes, and failure conclusions across GitHub Actions workflows.
        </p>
      </div>

      {builds.length === 0 ? (
        <div className="p-12 text-center border border-dashed border-border rounded-lg bg-card/20 space-y-2 font-mono">
          <Layers className="h-6 w-6 text-muted-foreground mx-auto" />
          <div className="text-xs text-foreground font-semibold">No Build History Recorded</div>
          <p className="text-[11px] text-muted-foreground max-w-md mx-auto">
            GitHub Actions workflow runs will automatically correlate with commits and populate build executions here.
          </p>
        </div>
      ) : (
        <div className="space-y-3 font-mono text-xs">
          <div className="text-xs font-semibold text-muted-foreground uppercase px-1">
            Build Records ({builds.length})
          </div>

          <div className="space-y-2">
            {builds.map((b) => (
              <div
                key={b.id}
                className="p-4 rounded-lg bg-card border border-border flex flex-col md:flex-row md:items-center justify-between gap-4 hover:border-border/80 transition-colors"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2 font-semibold text-foreground text-sm">
                    <span>Build #{b.build_number ?? "1"}</span>
                    <span className="text-[11px] font-normal text-muted-foreground">
                      sha:{b.commit_sha.slice(0, 8)}
                    </span>
                    <StatusBadge status={b.status} />
                  </div>
                  {b.logs_summary && (
                    <div className="text-[11px] text-muted-foreground">
                      {b.logs_summary}
                    </div>
                  )}
                  <div className="text-[10px] text-muted-foreground">
                    Created: {formatDate(b.created_at)}
                  </div>
                </div>

                <div className="flex items-center gap-4 text-xs font-mono">
                  <div>
                    <span className="text-[10px] uppercase text-muted-foreground block">Duration</span>
                    <span className="text-foreground">
                      {b.duration_seconds ? `${b.duration_seconds.toFixed(1)}s` : "—"}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase text-muted-foreground block">Tests</span>
                    <span className="text-emerald-400 font-bold">{b.tests_passed} passed</span> /{" "}
                    <span className="text-rose-400 font-bold">{b.tests_failed} failed</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
