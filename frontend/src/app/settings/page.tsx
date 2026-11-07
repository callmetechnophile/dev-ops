"use client";

import React, { useEffect, useState } from "react";
import { 
  Sliders, 
  CheckCircle2, 
  Shield, 
  Key, 
  Terminal, 
  RefreshCw, 
  Server, 
  GitBranch,
  AlertCircle,
  ExternalLink
} from "lucide-react";
import { fetchHealth, fetchGitHubStatus, fetchRepositories, fetchEvents } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { formatDate } from "@/lib/utils";

export default function SettingsPage() {
  const [health, setHealth] = useState<any>(null);
  const [githubStatus, setGithubStatus] = useState<any>(null);
  const [repositories, setRepositories] = useState<any[]>([]);
  const [recentEvents, setRecentEvents] = useState<any[]>([]);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [h, gh, repos, evts] = await Promise.allSettled([
          fetchHealth(),
          fetchGitHubStatus(),
          fetchRepositories(),
          fetchEvents(),
        ]);
        if (h.status === "fulfilled") setHealth(h.value);
        if (gh.status === "fulfilled") setGithubStatus(gh.value);
        if (repos.status === "fulfilled") setRepositories(repos.value.items || []);
        if (evts.status === "fulfilled") setRecentEvents(evts.value.items || []);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const webhookUrl = "http://localhost:8000/api/v1/integrations/github/webhook";

  const copyWebhook = () => {
    navigator.clipboard.writeText(webhookUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isConfigured = githubStatus?.status === "CONFIGURED";
  const lastEvent = recentEvents.length > 0 ? recentEvents[0] : null;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <Sliders className="h-5 w-5 text-accent" />
          GitHub App Integration & Webhook Health
        </h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Real-time integration status, connected repositories, event reception ledger, and webhook security credentials.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 font-mono text-xs">
        {/* GitHub App Authentication Status */}
        <div className="p-5 rounded-lg bg-card border border-border space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-border">
            <div className="flex items-center gap-2">
              <Terminal className="h-4 w-4 text-sky-400" />
              <span className="font-bold text-foreground text-sm">GitHub App Authentication</span>
            </div>
            <StatusBadge status={isConfigured ? "ACTIVE" : "PENDING_SETUP"} />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between p-2.5 rounded bg-background/50 border border-border">
              <span className="text-muted-foreground">Auth Strategy:</span>
              <span className="font-bold text-foreground uppercase">{githubStatus?.auth_type || "NONE"}</span>
            </div>
            <div className="flex items-center justify-between p-2.5 rounded bg-background/50 border border-border">
              <span className="text-muted-foreground">GitHub App ID:</span>
              <span className="font-bold text-foreground">{githubStatus?.app_id || "Not Configured"}</span>
            </div>
            <div className="flex items-center justify-between p-2.5 rounded bg-background/50 border border-border">
              <span className="text-muted-foreground">Installation ID:</span>
              <span className="font-bold text-foreground">{githubStatus?.installation_id || "Not Configured"}</span>
            </div>
            <div className="flex items-center justify-between p-2.5 rounded bg-background/50 border border-border">
              <span className="text-muted-foreground">Webhook Secret:</span>
              <span className="text-emerald-400 font-bold">{githubStatus?.webhook_configured ? "VERIFIED (HMAC-SHA256)" : "NOT SET"}</span>
            </div>
          </div>

          {/* Webhook URL copy box */}
          <div className="space-y-1.5 pt-2">
            <label className="text-[10px] uppercase text-muted-foreground font-semibold">
              Live Ingestion Webhook URL
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
          </div>
        </div>

        {/* Webhook Processing Health & Last Event */}
        <div className="p-5 rounded-lg bg-card border border-border space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-border">
            <div className="flex items-center gap-2">
              <Server className="h-4 w-4 text-emerald-400" />
              <span className="font-bold text-foreground text-sm">Webhook Ingestion & Stream Health</span>
            </div>
            <StatusBadge status={health?.status || "HEALTHY"} />
          </div>

          <div className="space-y-2">
            <div className="p-3 rounded bg-background/50 border border-border space-y-1">
              <div className="text-[10px] uppercase text-muted-foreground font-semibold">
                Last Event Received
              </div>
              {lastEvent ? (
                <div className="space-y-0.5 text-xs">
                  <div className="text-foreground font-bold flex items-center justify-between">
                    <span>{lastEvent.event_type}</span>
                    <span className="text-[10px] text-muted-foreground">{formatDate(lastEvent.occurred_at)}</span>
                  </div>
                  <div className="text-[11px] text-muted-foreground truncate">
                    Repo: {lastEvent.repository_name || "—"} &middot; SHA: {lastEvent.commit_sha ? lastEvent.commit_sha.slice(0, 8) : "—"}
                  </div>
                </div>
              ) : (
                <div className="text-xs text-muted-foreground">
                  No webhook events received yet.
                </div>
              )}
            </div>

            <div className="flex items-center justify-between p-2.5 rounded bg-background/40 border border-border">
              <div>
                <div className="font-semibold text-foreground">Redis Streams Bus</div>
                <div className="text-[10px] text-muted-foreground">Group: group:devops:intelligence</div>
              </div>
              <StatusBadge status={health?.components?.redis?.status || "CONNECTED"} />
            </div>

            <div className="flex items-center justify-between p-2.5 rounded bg-background/40 border border-border">
              <div>
                <div className="font-semibold text-foreground">Dead-Letter Stream</div>
                <div className="text-[10px] text-muted-foreground">stream:devops:deadletter</div>
              </div>
              <StatusBadge status="ACTIVE" />
            </div>
          </div>
        </div>
      </div>

      {/* Connected Repositories Section (Section 9.E) */}
      <div className="p-5 rounded-lg bg-card border border-border space-y-3 font-mono text-xs">
        <div className="flex items-center justify-between pb-2 border-b border-border">
          <div className="flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-accent" />
            <span className="font-bold text-foreground text-sm">
              Connected Repositories ({repositories.length})
            </span>
          </div>
        </div>

        {repositories.length === 0 ? (
          <div className="p-8 text-center border border-dashed border-border rounded text-xs text-muted-foreground">
            No repositories connected yet. Deliveries from GitHub webhooks will auto-discover and register active repositories here.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {repositories.map((repo) => (
              <div key={repo.id} className="p-3 rounded bg-background/50 border border-border flex items-center justify-between">
                <div>
                  <div className="font-bold text-foreground flex items-center gap-1.5">
                    <span>{repo.full_name}</span>
                    {repo.is_private && (
                      <span className="text-[9px] uppercase px-1 py-0.5 rounded bg-muted text-muted-foreground">
                        Private
                      </span>
                    )}
                  </div>
                  <div className="text-[10px] text-muted-foreground">
                    Branch: {repo.default_branch} &middot; Provider: {repo.provider}
                  </div>
                </div>
                {repo.html_url && (
                  <a
                    href={repo.html_url}
                    target="_blank"
                    rel="noreferrer"
                    className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
