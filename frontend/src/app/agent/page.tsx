"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock,
  Cpu,
  FileCode,
  Flame,
  GitCommit,
  Layers,
  Play,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  Sliders,
  Sparkles,
  Workflow,
  XCircle,
} from "lucide-react";
import { fetchAgentExecutions, triggerAgentExecution } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export default function AgentControlCenterPage() {
  const [executions, setExecutions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [triggerModalOpen, setTriggerModalOpen] = useState(false);
  const [deploymentIdInput, setDeploymentIdInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [triggerError, setTriggerError] = useState<string | null>(null);

  async function loadData() {
    setLoading(true);
    try {
      const data = await fetchAgentExecutions({
        status: statusFilter === "ALL" ? undefined : statusFilter,
        page_size: 50,
      });
      setExecutions(data.items || []);
    } catch (err) {
      console.error("Failed to load agent executions", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, [statusFilter]);

  async function handleTriggerExecution(e: React.FormEvent) {
    e.preventDefault();
    if (!deploymentIdInput.trim()) return;

    setIsSubmitting(true);
    setTriggerError(null);
    try {
      await triggerAgentExecution(deploymentIdInput.trim(), "MANUAL_DISPATCH");
      setTriggerModalOpen(false);
      setDeploymentIdInput("");
      await loadData();
    } catch (err: any) {
      setTriggerError(err.message || "Failed to trigger agent execution");
    } finally {
      setIsSubmitting(false);
    }
  }

  const filteredExecutions = executions.filter((item) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      item.id?.toLowerCase().includes(q) ||
      item.trigger_reference?.toLowerCase().includes(q) ||
      item.current_state?.toLowerCase().includes(q) ||
      item.environment?.toLowerCase().includes(q) ||
      item.deployment_id?.toLowerCase().includes(q)
    );
  });

  const activeCount = executions.filter((e) => e.execution_status === "RUNNING").length;
  const waitingCount = executions.filter((e) => e.execution_status === "WAITING_FOR_APPROVAL").length;
  const completedCount = executions.filter((e) => e.execution_status === "COMPLETED").length;
  const failedCount = executions.filter((e) => e.execution_status === "FAILED").length;

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2.5 py-0.5 text-xs font-semibold text-indigo-400">
              <Bot className="h-3.5 w-3.5" />
              Autonomous Orchestrator V1.0
            </span>
            <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs text-slate-300 font-mono">
              16-State Pipeline
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Predictive DevOps Agent Control Center
          </h1>
          <p className="text-sm text-slate-400">
            Coordinates pre-flight context collection, risk assessment, policy evaluation, human approval gateways, and outcome verification.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/settings/policies"
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/80 px-3.5 py-2 text-xs font-medium text-slate-300 hover:bg-slate-700 transition-colors"
          >
            <Shield className="h-3.5 w-3.5 text-indigo-400" />
            Deployment Policies
          </Link>

          <Link
            href="/approvals"
            className="inline-flex items-center gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3.5 py-2 text-xs font-semibold text-amber-300 hover:bg-amber-500/20 transition-colors"
          >
            <ShieldAlert className="h-3.5 w-3.5" />
            Approval Center ({waitingCount})
          </Link>

          <button
            onClick={() => setTriggerModalOpen(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 transition-colors shadow-lg shadow-indigo-600/20"
          >
            <Play className="h-4 w-4" />
            Dispatch Agent Run
          </button>
        </div>
      </div>

      {/* Top 4 KPI Metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
              Active Executions
            </span>
            <Activity className="h-4 w-4 text-indigo-400 animate-pulse" />
          </div>
          <p className="mt-2 text-3xl font-bold text-white">{activeCount}</p>
          <span className="text-xs text-slate-500">pipeline stages in-flight</span>
        </div>

        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium uppercase tracking-wider text-amber-300">
              Waiting for Approval
            </span>
            <ShieldAlert className="h-4 w-4 text-amber-400" />
          </div>
          <p className="mt-2 text-3xl font-bold text-amber-400">{waitingCount}</p>
          <span className="text-xs text-amber-200/70">gated on human sign-off</span>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
              Completed
            </span>
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          </div>
          <p className="mt-2 text-3xl font-bold text-white">{completedCount}</p>
          <span className="text-xs text-slate-500">verified lifecycle runs</span>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
              Failed / Interrupted
            </span>
            <XCircle className="h-4 w-4 text-rose-400" />
          </div>
          <p className="mt-2 text-3xl font-bold text-rose-400">{failedCount}</p>
          <span className="text-xs text-slate-500">error or policy halts</span>
        </div>
      </div>

      {/* State Machine Overview Bar */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Workflow className="h-4 w-4 text-indigo-400" />
            <h3 className="text-sm font-semibold text-white">Agent State Machine Architecture</h3>
          </div>
          <span className="text-xs text-slate-400 font-mono">Strict Deterministic Progression</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2 text-xs">
          {[
            { label: "1. Detect", state: "DEPLOYMENT_DETECTED" },
            { label: "2. Context", state: "CONTEXT_COLLECTION" },
            { label: "3. Validate", state: "CONTEXT_VALIDATION" },
            { label: "4. Memory", state: "HISTORICAL_RETRIEVAL" },
            { label: "5. Risk", state: "RISK_ASSESSMENT" },
            { label: "6. Policy", state: "POLICY_EVALUATION" },
            { label: "7. Recs", state: "RECOMMENDATION_GENERATION" },
            { label: "8. Approval", state: "WAITING_FOR_APPROVAL" },
            { label: "9. Sign-off", state: "APPROVED" },
            { label: "10. Reject", state: "REJECTED" },
            { label: "11. Expire", state: "EXPIRED" },
            { label: "12. Monitor", state: "POST_DEPLOYMENT_MONITORING" },
            { label: "13. Outcome", state: "OUTCOME_VERIFICATION" },
            { label: "14. Learn", state: "MEMORY_UPDATE" },
            { label: "15. Done", state: "COMPLETED" },
            { label: "16. Failed", state: "FAILED" },
          ].map((s, idx) => (
            <div
              key={idx}
              className="rounded-lg border border-slate-800 bg-slate-800/40 p-2 text-center"
            >
              <div className="font-medium text-slate-300 truncate">{s.label}</div>
              <div className="text-[10px] font-mono text-slate-500 truncate">{s.state}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 overflow-x-auto">
          {["ALL", "RUNNING", "WAITING_FOR_APPROVAL", "COMPLETED", "FAILED"].map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                statusFilter === status
                  ? "bg-indigo-600 text-white"
                  : "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white"
              }`}
            >
              {status.replace(/_/g, " ")}
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-64">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search executions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-slate-800 bg-slate-900/60 pl-9 pr-4 py-2 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Executions Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden backdrop-blur-sm">
        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <div className="flex items-center gap-3 text-slate-400">
              <RefreshCw className="h-5 w-5 animate-spin text-indigo-400" />
              <span>Loading agent executions...</span>
            </div>
          </div>
        ) : filteredExecutions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-800/50 text-xs uppercase text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="px-6 py-3">Execution ID</th>
                  <th className="px-6 py-3">Current State</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3">Environment</th>
                  <th className="px-6 py-3">Trigger / Deployment</th>
                  <th className="px-6 py-3">Recommendations</th>
                  <th className="px-6 py-3">Started</th>
                  <th className="px-6 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {filteredExecutions.map((exec) => {
                  const isWaiting = exec.execution_status === "WAITING_FOR_APPROVAL";
                  const isCompleted = exec.execution_status === "COMPLETED";
                  const isFailed = exec.execution_status === "FAILED";

                  return (
                    <tr key={exec.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-6 py-4 font-mono font-medium text-white flex items-center gap-2">
                        <Bot className="h-4 w-4 text-indigo-400 shrink-0" />
                        <Link
                          href={`/agent/executions/${exec.id}`}
                          className="hover:underline text-indigo-300"
                        >
                          #{exec.id.slice(0, 8)}
                        </Link>
                      </td>

                      <td className="px-6 py-4">
                        <span className="font-mono text-xs font-semibold text-indigo-300 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                          {exec.current_state}
                        </span>
                      </td>

                      <td className="px-6 py-4">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium border ${
                            isWaiting
                              ? "bg-amber-500/10 text-amber-300 border-amber-500/30"
                              : isCompleted
                              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                              : isFailed
                              ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                              : "bg-indigo-500/10 text-indigo-400 border-indigo-500/30"
                          }`}
                        >
                          {exec.execution_status}
                        </span>
                      </td>

                      <td className="px-6 py-4 text-xs font-mono text-slate-300">
                        {exec.environment}
                      </td>

                      <td className="px-6 py-4 text-xs font-mono text-slate-400">
                        <div>{exec.trigger_type}</div>
                        <div className="text-[11px] text-slate-500 truncate max-w-[140px]">
                          {exec.trigger_reference}
                        </div>
                      </td>

                      <td className="px-6 py-4 text-xs text-slate-300">
                        {exec.recommendations_count} proposed
                      </td>

                      <td className="px-6 py-4 text-xs text-slate-400">
                        {formatDate(exec.started_at)}
                      </td>

                      <td className="px-6 py-4 text-right">
                        <Link
                          href={`/agent/executions/${exec.id}`}
                          className="inline-flex items-center gap-1 rounded bg-slate-800 px-2.5 py-1 text-xs font-medium text-slate-200 hover:bg-slate-700"
                        >
                          Inspect Run
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-12 text-center text-slate-400">
            <Bot className="mx-auto h-12 w-12 text-slate-600 mb-3" />
            <p className="text-base font-semibold text-white">No Agent Executions Found</p>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              Agent executions are triggered automatically via deployment events or manually dispatched using the button above.
            </p>
          </div>
        )}
      </div>

      {/* Trigger Modal */}
      {triggerModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Play className="h-4 w-4 text-indigo-400" />
                Dispatch Agent Execution
              </h3>
              <button
                onClick={() => setTriggerModalOpen(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleTriggerExecution} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Deployment ID (UUID)
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. 00000000-0000-0000-0000-000000000001"
                  value={deploymentIdInput}
                  onChange={(e) => setDeploymentIdInput(e.target.value)}
                  className="w-full rounded-lg border border-slate-800 bg-slate-800/80 px-3 py-2 text-xs font-mono text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  The agent will gather context, assess risk, evaluate policy, and generate recommendations.
                </p>
              </div>

              {triggerError && (
                <div className="rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300">
                  {triggerError}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setTriggerModalOpen(false)}
                  className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="rounded-lg bg-indigo-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
                >
                  {isSubmitting ? "Dispatching..." : "Start Agent Analysis"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
