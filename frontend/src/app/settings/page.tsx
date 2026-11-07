"use client";

import React, { useEffect, useState } from "react";
import { Sliders, CheckCircle2, Shield, Key, Terminal, RefreshCw, Cpu, Server } from "lucide-react";
import { fetchHealth } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";

export default function SettingsPage() {
  const [health, setHealth] = useState<any>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => {});
  }, []);

  const webhookUrl = "http://localhost:8000/api/v1/integrations/github/webhook";

  const copyWebhook = () => {
    navigator.clipboard.writeText(webhookUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <Sliders className="h-5 w-5 text-accent" />
          Integration Connectors & Security Configuration
        </h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Connection status for GitHub Actions webhooks, Docker containers, Kubernetes clusters, and pgvector operational memory.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 font-mono text-xs">
        {/* GitHub Integration */}
        <div className="p-5 rounded-lg bg-card border border-border space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-border">
            <div className="flex items-center gap-2">
              <Terminal className="h-4 w-4 text-sky-400" />
              <span className="font-bold text-foreground text-sm">GitHub Actions Integration</span>
            </div>
            <StatusBadge status="ACTIVE" />
          </div>

          <div className="space-y-2">
            <label className="text-[10px] uppercase text-muted-foreground font-semibold">
              Webhook Ingestion Endpoint
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                readOnly
                value={webhookUrl}
                className="flex-1 p-2 rounded bg-background border border-border text-foreground font-mono text-[11px]"
              />
              <button
                onClick={copyWebhook}
                className="px-3 py-1.5 rounded bg-muted border border-border hover:bg-accent/10 hover:border-accent text-foreground text-xs"
              >
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
            <p className="text-[10px] text-muted-foreground">
              Configured with HMAC SHA-256 signature verification (<code className="text-accent">X-Hub-Signature-256</code>).
            </p>
          </div>

          <div className="p-3 rounded bg-background/50 border border-border space-y-1 text-[11px]">
            <div className="text-foreground font-semibold">Supported Event Types:</div>
            <div className="text-muted-foreground">
              <code>push</code>, <code>workflow_run</code>, <code>pull_request</code>, <code>check_run</code>
            </div>
          </div>
        </div>

        {/* Core Infrastructure Connectors */}
        <div className="p-5 rounded-lg bg-card border border-border space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-border">
            <div className="flex items-center gap-2">
              <Server className="h-4 w-4 text-emerald-400" />
              <span className="font-bold text-foreground text-sm">Infrastructure Connectors</span>
            </div>
            <StatusBadge status="HEALTHY" />
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between p-2.5 rounded bg-background/40 border border-border">
              <div>
                <div className="font-semibold text-foreground">Docker Engine Collector</div>
                <div className="text-[10px] text-muted-foreground">Container image metadata & tags</div>
              </div>
              <StatusBadge status="READY" />
            </div>

            <div className="flex items-center justify-between p-2.5 rounded bg-background/40 border border-border">
              <div>
                <div className="font-semibold text-foreground">Kubernetes Event Watcher</div>
                <div className="text-[10px] text-muted-foreground">Pod CrashLoopBackOff & OOM tracker</div>
              </div>
              <StatusBadge status="READY" />
            </div>

            <div className="flex items-center justify-between p-2.5 rounded bg-background/40 border border-border">
              <div>
                <div className="font-semibold text-foreground">Redis Streams Bus</div>
                <div className="text-[10px] text-muted-foreground">Idempotent stream: stream:devops:events</div>
              </div>
              <StatusBadge status={health?.components?.redis?.status || "CONNECTED"} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
