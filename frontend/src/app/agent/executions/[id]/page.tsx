"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  Bot,
  CheckCircle2,
  Clock,
  Compass,
  Cpu,
  FileCode,
  Flame,
  GitCommit,
  GitFork,
  HelpCircle,
  History,
  Layers,
  Lightbulb,
  Network,
  Play,
  RefreshCw,
  Scale,
  Shield,
  ShieldAlert,
  Sliders,
  TrendingDown,
  TrendingUp,
  Workflow,
  XCircle,
} from "lucide-react";
import {
  fetchAgentExecution,
  fetchExecutionTimeline,
  fetchExecutionRecommendations,
  fetchExecutionPolicyEvaluations,
  fetchExecutionOutcomes,
  advanceExecutionOutcome,
} from "@/lib/api";
import { formatDate } from "@/lib/utils";

export default function AgentExecutionDetailPage() {
  const params = useParams();
  const id = params?.id as string;

  const [execution, setExecution] = useState<any | null>(null);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [recommendations, setRecommendations] = useState<any[]>([]);
  const [policyEvaluations, setPolicyEvaluations] = useState<any[]>([]);
  const [outcomes, setOutcomes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [advancing, setAdvancing] = useState(false);
  const [actionMessage, setActionMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);
  const [activeTab, setActiveTab] = useState<"timeline" | "context" | "policies" | "recommendations" | "outcomes">("timeline");

  async function loadData() {
    if (!id) return;
    setLoading(true);
    try {
      const [execData, timelineData, recsData, evalsData, outcomesData] = await Promise.all([
        fetchAgentExecution(id),
        fetchExecutionTimeline(id),
        fetchExecutionRecommendations(id),
        fetchExecutionPolicyEvaluations(id),
        fetchExecutionOutcomes(id),
      ]);
      setExecution(execData);
      setTimeline(timelineData || []);
      setRecommendations(recsData || []);
      setPolicyEvaluations(evalsData || []);
      setOutcomes(outcomesData || []);
    } catch (err) {
      console.error("Failed to load execution detail", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, [id]);

  async function handleAdvanceOutcome() {
    setAdvancing(true);
    setActionMessage(null);
    try {
      const res = await advanceExecutionOutcome(id, 60);
      setActionMessage({
        text: res.message || "Outcome verified and memory updated.",
        type: "success",
      });
      await loadData();
    } catch (err: any) {
      setActionMessage({
        text: err.message || "Failed to advance outcome",
        type: "error",
      });
    } finally {
      setAdvancing(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="flex items-center gap-3 text-slate-400">
          <RefreshCw className="h-5 w-5 animate-spin text-indigo-400" />
          <span>Synthesizing agent state machine and execution telemetry...</span>
        </div>
      </div>
    );
  }

  if (!execution) {
    return (
      <div className="mx-auto max-w-4xl p-8 text-center">
        <Bot className="mx-auto h-12 w-12 text-rose-400 mb-4" />
        <h2 className="text-xl font-bold text-white mb-2">Agent Execution Not Found</h2>
        <p className="text-slate-400 mb-6">The requested agent execution ID does not exist or belongs to another tenant.</p>
        <Link
          href="/agent"
          className="inline-flex items-center gap-2 rounded-lg bg-slate-800 px-4 py-2 text-sm text-slate-200 hover:bg-slate-700"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Agent Control Center
        </Link>
      </div>
    );
  }

  const isWaiting = execution.execution_status === "WAITING_FOR_APPROVAL";
  const isCompleted = execution.execution_status === "COMPLETED";
  const isFailed = execution.execution_status === "FAILED";
  const canAdvanceOutcome = execution.current_state === "POST_DEPLOYMENT_MONITORING" || execution.current_state === "APPROVED";

  const contextSnap = execution.context_snapshot || {};
  const ghContext = contextSnap.github_context || {};
  const opMemory = contextSnap.operational_memory || {};
  const predIntel = contextSnap.predictive_intelligence || {};
  const infraContext = contextSnap.infrastructure_context || {};

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      {/* Breadcrumb & Navigation */}
      <div className="flex items-center justify-between">
        <Link
          href="/agent"
          className="inline-flex items-center gap-2 text-sm text-slate-400 transition-colors hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Agent Control Center
        </Link>

        <div className="flex items-center gap-3">
          {canAdvanceOutcome && (
            <button
              onClick={handleAdvanceOutcome}
              disabled={advancing}
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50 transition-colors shadow-lg shadow-emerald-600/20"
            >
              {advancing ? (
                <>
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  Verifying Outcome...
                </>
              ) : (
                <>
                  <Play className="h-3.5 w-3.5" />
                  Verify Outcome & Update Memory
                </>
              )}
            </button>
          )}

          {isWaiting && (
            <Link
              href="/approvals"
              className="inline-flex items-center gap-2 rounded-lg bg-amber-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-amber-500 transition-colors shadow-lg shadow-amber-600/20"
            >
              <ShieldAlert className="h-3.5 w-3.5" />
              Resolve in Approval Center
            </Link>
          )}
        </div>
      </div>

      {/* Action Notification Alert */}
      {actionMessage && (
        <div
          className={`flex items-start gap-3 rounded-xl border p-4 text-sm ${
            actionMessage.type === "success"
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              : "border-rose-500/30 bg-rose-500/10 text-rose-300"
          }`}
        >
          {actionMessage.type === "success" ? (
            <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-400" />
          ) : (
            <AlertCircle className="h-5 w-5 shrink-0 text-rose-400" />
          )}
          <p className="font-medium">{actionMessage.text}</p>
        </div>
      )}

      {/* Header Banner */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="font-mono text-xs font-bold text-indigo-300 bg-indigo-500/10 px-3 py-1 rounded-full border border-indigo-500/30 flex items-center gap-1.5">
                <Workflow className="h-3.5 w-3.5" />
                STATE: {execution.current_state}
              </span>

              <span
                className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold border ${
                  isWaiting
                    ? "bg-amber-500/10 text-amber-300 border-amber-500/30"
                    : isCompleted
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                    : isFailed
                    ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                    : "bg-indigo-500/10 text-indigo-400 border-indigo-500/30"
                }`}
              >
                {execution.execution_status}
              </span>

              <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs text-slate-300 font-mono">
                {execution.environment}
              </span>
            </div>

            <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              Agent Execution
              <span className="text-sm font-normal text-slate-400 font-mono">
                #{execution.id.slice(0, 8)}
              </span>
            </h1>

            <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400">
              <span className="flex items-center gap-1">
                <Activity className="h-3.5 w-3.5 text-slate-500" />
                Trigger: <code className="text-slate-300 font-mono">{execution.trigger_type}</code>
              </span>
              <span className="flex items-center gap-1">
                <GitCommit className="h-3.5 w-3.5 text-slate-500" />
                Reference: <code className="text-slate-300 font-mono">{execution.trigger_reference?.slice(0, 10)}</code>
              </span>
              <span className="flex items-center gap-1">
                <Clock className="h-3.5 w-3.5 text-slate-500" />
                Started: {formatDate(execution.started_at)}
              </span>
              {execution.completed_at && (
                <span className="flex items-center gap-1">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                  Completed: {formatDate(execution.completed_at)}
                </span>
              )}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {execution.deployment_id && (
              <Link
                href={`/risk/${predIntel.assessment_id || ""}`}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs font-medium text-slate-200 hover:bg-slate-700 transition-colors"
              >
                <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
                Risk Assessment
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-800">
        <nav className="flex space-x-6 overflow-x-auto">
          <button
            onClick={() => setActiveTab("timeline")}
            className={`pb-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 whitespace-nowrap ${
              activeTab === "timeline"
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <History className="h-4 w-4" />
            Transition Timeline ({timeline.length})
          </button>

          <button
            onClick={() => setActiveTab("context")}
            className={`pb-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 whitespace-nowrap ${
              activeTab === "context"
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Layers className="h-4 w-4" />
            Collected Context
            {execution.missing_context?.length > 0 && (
              <span className="ml-1 rounded-full bg-amber-500/20 text-amber-300 px-1.5 py-0.2 text-[10px] font-mono">
                {execution.missing_context.length} missing
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab("policies")}
            className={`pb-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 whitespace-nowrap ${
              activeTab === "policies"
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Shield className="h-4 w-4" />
            Policy Evaluations ({policyEvaluations.length})
          </button>

          <button
            onClick={() => setActiveTab("recommendations")}
            className={`pb-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 whitespace-nowrap ${
              activeTab === "recommendations"
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Lightbulb className="h-4 w-4" />
            Recommendations ({recommendations.length})
          </button>

          <button
            onClick={() => setActiveTab("outcomes")}
            className={`pb-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 whitespace-nowrap ${
              activeTab === "outcomes"
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <CheckCircle2 className="h-4 w-4" />
            Outcome Verification ({outcomes.length})
          </button>
        </nav>
      </div>

      {/* Tab 1: Timeline */}
      {activeTab === "timeline" && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-white">State Transition Audit Trail</h3>
            <span className="text-xs text-slate-400 font-mono">Strict Invariant Ordering</span>
          </div>

          <div className="relative border-l border-slate-800 ml-4 space-y-6">
            {timeline.map((step, idx) => (
              <div key={idx} className="relative pl-6">
                <div className="absolute -left-2 top-1.5 h-4 w-4 rounded-full border border-indigo-500/40 bg-indigo-500/20 flex items-center justify-center">
                  <div className="h-1.5 w-1.5 rounded-full bg-indigo-400" />
                </div>

                <div className="rounded-lg border border-slate-800 bg-slate-800/40 p-4 space-y-2">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-slate-400">
                        {step.previous_state}
                      </span>
                      <span className="text-slate-600">→</span>
                      <span className="font-mono text-xs font-bold text-indigo-300 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                        {step.next_state}
                      </span>
                    </div>
                    <span className="text-[11px] text-slate-400 font-mono">
                      {formatDate(step.created_at)}
                    </span>
                  </div>

                  <p className="text-xs text-slate-300">{step.transition_reason}</p>

                  <div className="flex items-center gap-4 text-[10px] text-slate-500">
                    <span>Triggered by: <code className="text-slate-400 font-mono">{step.triggered_by}</code></span>
                    {step.payload && Object.keys(step.payload).length > 0 && (
                      <span className="font-mono">Payload: {JSON.stringify(step.payload)}</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 2: Collected Context */}
      {activeTab === "context" && (
        <div className="space-y-6">
          {/* Missing context warning banner */}
          {execution.missing_context && execution.missing_context.length > 0 && (
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-200 space-y-1">
              <div className="font-semibold flex items-center gap-1.5">
                <AlertTriangle className="h-4 w-4 text-amber-400" />
                Missing Context Fields Identified:
              </div>
              <ul className="list-disc pl-5 space-y-0.5">
                {execution.missing_context.map((field: string, idx: number) => (
                  <li key={idx} className="font-mono">{field}</li>
                ))}
              </ul>
              <p className="text-[11px] text-amber-300/80 pt-1">
                The agent explicitly distinguished unavailable data from negative signals, preventing false assumptions.
              </p>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* GitHub Context */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-3">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <GitCommit className="h-4 w-4 text-indigo-400" />
                GitHub & Code Changes
              </h4>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between border-b border-slate-800/60 pb-1.5">
                  <span className="text-slate-400">Repository:</span>
                  <span className="font-mono text-white">{ghContext.repository?.full_name || "N/A"}</span>
                </div>
                <div className="flex justify-between border-b border-slate-800/60 pb-1.5">
                  <span className="text-slate-400">Commit SHA:</span>
                  <span className="font-mono text-white">{ghContext.commit_sha || "N/A"}</span>
                </div>
                <div className="flex justify-between border-b border-slate-800/60 pb-1.5">
                  <span className="text-slate-400">Lines Added / Deleted:</span>
                  <span className="font-mono text-emerald-400">+{ghContext.commit?.additions || 0}</span>
                  <span className="font-mono text-rose-400">-{ghContext.commit?.deletions || 0}</span>
                </div>
                <div className="flex justify-between border-b border-slate-800/60 pb-1.5">
                  <span className="text-slate-400">Build Status:</span>
                  <span className="font-mono text-white">{ghContext.build?.status || "telemetry missing"}</span>
                </div>
              </div>
            </div>

            {/* Predictive Intelligence */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-3">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <Scale className="h-4 w-4 text-indigo-400" />
                Predictive Intelligence
              </h4>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between border-b border-slate-800/60 pb-1.5">
                  <span className="text-slate-400">Risk Level:</span>
                  <span className="font-bold text-white">{predIntel.risk_level || "ASSESSED"}</span>
                </div>
                <div className="flex justify-between border-b border-slate-800/60 pb-1.5">
                  <span className="text-slate-400">Failure Probability:</span>
                  <span className="font-mono text-indigo-300">
                    {predIntel.failure_probability !== null && predIntel.failure_probability !== undefined
                      ? `${(predIntel.failure_probability * 100).toFixed(1)}%`
                      : "Uncalibrated Baseline"}
                  </span>
                </div>
                <div className="flex justify-between border-b border-slate-800/60 pb-1.5">
                  <span className="text-slate-400">Operational Blast Radius:</span>
                  <span className="font-mono text-rose-400">
                    {predIntel.operational_impact_score !== undefined
                      ? `${(predIntel.operational_impact_score * 100).toFixed(0)}/100 (${predIntel.impact_category})`
                      : "N/A"}
                  </span>
                </div>
              </div>
            </div>

            {/* Operational Memory */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-3">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <Compass className="h-4 w-4 text-indigo-400" />
                Recalled Operational Memory
              </h4>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between border-b border-slate-800/60 pb-1.5">
                  <span className="text-slate-400">Similar Incidents:</span>
                  <span className="font-mono text-white">{opMemory.similar_incidents?.length || 0} recalled</span>
                </div>
                <div className="flex justify-between border-b border-slate-800/60 pb-1.5">
                  <span className="text-slate-400">Confirmed Root Causes:</span>
                  <span className="font-mono text-white">{opMemory.confirmed_root_causes?.length || 0} matched</span>
                </div>
                <div className="flex justify-between border-b border-slate-800/60 pb-1.5">
                  <span className="text-slate-400">Verified Lessons:</span>
                  <span className="font-mono text-white">{opMemory.verified_lessons?.length || 0} loaded</span>
                </div>
              </div>
            </div>

            {/* Infrastructure & Topology */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-3">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <Network className="h-4 w-4 text-indigo-400" />
                Infrastructure & Topology
              </h4>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between border-b border-slate-800/60 pb-1.5">
                  <span className="text-slate-400">Service Tier:</span>
                  <span className="font-mono text-white">{infraContext.target_service?.tier || "tier-2"}</span>
                </div>
                <div className="flex justify-between border-b border-slate-800/60 pb-1.5">
                  <span className="text-slate-400">Downstream Dependencies:</span>
                  <span className="font-mono text-white">{infraContext.downstream_dependencies?.length || 0} services</span>
                </div>
                <div className="flex justify-between border-b border-slate-800/60 pb-1.5">
                  <span className="text-slate-400">Upstream Dependencies:</span>
                  <span className="font-mono text-white">{infraContext.upstream_dependencies?.length || 0} services</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Policies */}
      {activeTab === "policies" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-white">Policy Evaluation Engine Results</h3>
                <p className="text-xs text-slate-400">
                  Deterministic enterprise policies evaluated against deployment context.
                </p>
              </div>
            </div>

            {policyEvaluations.map((pe, idx) => (
              <div
                key={idx}
                className="rounded-lg border border-slate-800 bg-slate-800/40 p-4 space-y-3"
              >
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Shield className="h-4 w-4 text-indigo-400" />
                    <span className="text-sm font-semibold text-white">{pe.policy_name}</span>
                    <span className="font-mono text-[10px] text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                      {pe.policy_version}
                    </span>
                  </div>

                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
                      pe.outcome === "ALLOW_WITHOUT_ADDITIONAL_REVIEW"
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                        : pe.outcome === "RECOMMEND_DELAY"
                        ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                        : "bg-amber-500/10 text-amber-300 border-amber-500/30"
                    }`}
                  >
                    {pe.outcome}
                  </span>
                </div>

                {pe.evidence?.reasons && (
                  <div className="space-y-1">
                    <span className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
                      Evaluation Reasons:
                    </span>
                    <ul className="list-disc pl-5 text-xs text-slate-300 space-y-1">
                      {pe.evidence.reasons.map((r: string, rIdx: number) => (
                        <li key={rIdx}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 4: Recommendations */}
      {activeTab === "recommendations" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm space-y-4">
            <h3 className="text-base font-semibold text-white">Actionable Mitigation Recommendations</h3>

            {recommendations.map((rec, idx) => (
              <div
                key={idx}
                className="rounded-lg border border-slate-800 bg-slate-800/40 p-4 space-y-3"
              >
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-semibold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                      {rec.recommendation_type}
                    </span>
                    <h4 className="text-sm font-semibold text-white">{rec.title}</h4>
                  </div>
                  <span className="text-xs text-slate-400">
                    Confidence: <strong className="text-indigo-300 font-mono">{(rec.confidence_score * 100).toFixed(0)}%</strong>
                  </span>
                </div>

                <p className="text-xs text-slate-300">{rec.explanation || rec.rationale}</p>

                {rec.mitigation_steps && rec.mitigation_steps.length > 0 && (
                  <div className="rounded bg-slate-900/60 p-3 border border-slate-800 text-xs text-slate-300 space-y-1">
                    <span className="font-semibold text-slate-400 text-[11px] uppercase tracking-wider">
                      Required Mitigation Procedure:
                    </span>
                    <ul className="list-decimal pl-5 space-y-1">
                      {rec.mitigation_steps.map((step: string, sIdx: number) => (
                        <li key={sIdx}>{step}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 5: Outcomes */}
      {activeTab === "outcomes" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-white">Post-Deployment Outcome Verification</h3>
                <p className="text-xs text-slate-400">
                  Observed signals from deployment telemetry, incidents, and observation window monitoring.
                </p>
              </div>

              {canAdvanceOutcome && (
                <button
                  onClick={handleAdvanceOutcome}
                  disabled={advancing}
                  className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-500"
                >
                  {advancing ? "Verifying..." : "Verify Outcome Now"}
                </button>
              )}
            </div>

            {outcomes.length > 0 ? (
              <div className="space-y-3">
                {outcomes.map((obs, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-800/40 p-4"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-semibold text-slate-400">
                          {obs.observation_type}
                        </span>
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold border ${
                            obs.observation_value === "SUCCESS"
                              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                              : obs.observation_value === "FAILURE" || obs.observation_value === "INCIDENT"
                              ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                              : "bg-slate-800 text-slate-400 border-slate-700"
                          }`}
                        >
                          {obs.observation_value}
                        </span>
                      </div>
                      <div className="text-[11px] font-mono text-slate-400">
                        {JSON.stringify(obs.evidence_reference)}
                      </div>
                    </div>
                    <span className="text-xs text-slate-500 font-mono">
                      {formatDate(obs.observed_at)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-slate-400">
                <CheckCircle2 className="mx-auto h-8 w-8 text-slate-600 mb-2" />
                <p className="text-sm">No post-deployment outcome observations recorded yet.</p>
                <p className="text-xs text-slate-500 mt-1">
                  Once the deployment is authorized and rollout begins, outcome observations will populate here.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
