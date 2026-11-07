"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { 
  CheckCheck, 
  XCircle, 
  ShieldCheck, 
  Clock, 
  CheckCircle2, 
  AlertTriangle, 
  Fingerprint, 
  Bot, 
  ArrowUpRight, 
  HelpCircle,
  AlertOctagon,
  FileText
} from "lucide-react";
import { fetchApprovals, submitApprovalDecision } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { formatDate } from "@/lib/utils";

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [justifications, setJustifications] = useState<{ [key: string]: string }>({});
  const [submitting, setSubmitting] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const params = statusFilter === "ALL" ? undefined : { status: statusFilter };
      const res = await fetchApprovals(params);
      setApprovals(res.items || []);
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || "Failed to load approval requests");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [statusFilter]);

  const handleDecision = async (
    requestId: string,
    action: "APPROVE" | "REJECT" | "REQUEST_MORE_INFORMATION" | "ESCALATE"
  ) => {
    const notes = (justifications[requestId] || "").trim();
    if (!notes) {
      setErrorMsg("A written justification / audit note is strictly required for governance decisions.");
      return;
    }
    setErrorMsg(null);
    setSuccessMsg(null);
    setSubmitting(requestId);

    try {
      // Default authorized approver / lead engineer UUID
      const userId = "00000000-0000-0000-0000-000000000002";
      const decisionRecord = await submitApprovalDecision(requestId, action, notes, userId);
      setSuccessMsg(
        `Action ${action} recorded with SHA-256 audit fingerprint: ${decisionRecord.audit_signature.slice(0, 16)}...`
      );
      setJustifications((prev) => ({ ...prev, [requestId]: "" }));
      await load();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to record approval decision");
    } finally {
      setSubmitting(null);
    }
  };

  const isExpired = (expiresAt?: string) => {
    if (!expiresAt) return false;
    return new Date(expiresAt).getTime() < Date.now();
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <CheckCheck className="h-5 w-5 text-emerald-400" />
            Human Approval Gate & Governance
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Strict human-in-the-loop operational boundary. The agent coordinates predictions and recommendations, but all production deployments require authorized cryptographic signatures.
          </p>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1.5 bg-card border border-border rounded-lg p-1 text-xs font-mono">
          {["ALL", "WAITING_FOR_APPROVAL", "APPROVED", "REJECTED", "EXPIRED"].map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`px-2.5 py-1 rounded transition-colors text-[11px] font-semibold ${
                statusFilter === status
                  ? "bg-accent/20 text-accent border border-accent/40"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {errorMsg && (
        <div className="p-3 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono flex items-center justify-between">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-rose-400 hover:text-rose-200">
            <XCircle className="h-4 w-4" />
          </button>
        </div>
      )}

      {successMsg && (
        <div className="p-3 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-mono flex items-center justify-between">
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-400 hover:text-emerald-200">
            <CheckCircle2 className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Approvals list */}
      <div className="space-y-4">
        {loading ? (
          <div className="p-12 text-center text-xs text-muted-foreground font-mono animate-pulse">
            Loading approval requests...
          </div>
        ) : approvals.length === 0 ? (
          <div className="p-12 text-center border border-dashed border-border rounded-lg bg-card/20 space-y-2 font-mono">
            <ShieldCheck className="h-6 w-6 text-emerald-400 mx-auto" />
            <div className="text-xs text-foreground font-semibold">No Approval Requests in this view</div>
            <p className="text-[11px] text-muted-foreground max-w-md mx-auto">
              When high-risk deployments or policy gates require human authorization, they are dispatched here for digital audit signing.
            </p>
          </div>
        ) : (
          approvals.map((req) => {
            const expired = isExpired(req.expires_at) || req.status === "EXPIRED";
            return (
              <div
                key={req.id}
                className="p-5 rounded-lg bg-card border border-border space-y-4 font-mono text-xs"
              >
                <div className="flex items-center justify-between pb-3 border-b border-border">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-foreground font-bold text-sm">
                        {req.requested_action}
                      </span>
                      {req.context_data?.environment && (
                        <span className="px-2 py-0.5 rounded text-[10px] bg-amber-500/10 text-amber-400 border border-amber-500/30 font-semibold uppercase">
                          {req.context_data.environment}
                        </span>
                      )}
                    </div>
                    <div className="text-muted-foreground text-[10px] flex items-center gap-3">
                      <span>Request ID: {req.id}</span>
                      <span>Deployment: {req.deployment_id.slice(0, 8)}...</span>
                      <span>Created: {formatDate(req.created_at)}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {req.execution_id && (
                      <Link
                        href={`/agent/executions/${req.execution_id}`}
                        className="flex items-center gap-1 px-2.5 py-1 rounded bg-accent/10 border border-accent/20 text-accent hover:bg-accent/20 text-[11px] font-semibold transition-colors"
                      >
                        <Bot className="h-3 w-3" />
                        Agent Execution
                        <ArrowUpRight className="h-3 w-3" />
                      </Link>
                    )}
                    <StatusBadge status={expired && req.status === "WAITING_FOR_APPROVAL" ? "EXPIRED" : req.status} />
                  </div>
                </div>

                {/* Metadata & Governance attributes */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-[11px]">
                  <div className="p-2 rounded bg-background/60 border border-border space-y-0.5">
                    <div className="text-[10px] text-muted-foreground uppercase">Policy Version</div>
                    <div className="font-semibold text-foreground">{req.policy_version || "v1.0.0"}</div>
                  </div>
                  <div className="p-2 rounded bg-background/60 border border-border space-y-0.5">
                    <div className="text-[10px] text-muted-foreground uppercase">Risk Model Version</div>
                    <div className="font-semibold text-foreground">{req.risk_assessment_version || "M4-Calibrated"}</div>
                  </div>
                  <div className="p-2 rounded bg-background/60 border border-border space-y-0.5">
                    <div className="text-[10px] text-muted-foreground uppercase">Expires At</div>
                    <div className={`font-semibold ${expired ? "text-rose-400" : "text-muted-foreground"}`}>
                      {req.expires_at ? formatDate(req.expires_at) : "No Expiry"}
                    </div>
                  </div>
                  <div className="p-2 rounded bg-background/60 border border-border space-y-0.5">
                    <div className="text-[10px] text-muted-foreground uppercase">Assigned Reviewer</div>
                    <div className="font-semibold text-accent">
                      {req.assigned_reviewer_id ? `${req.assigned_reviewer_id.slice(0, 8)}...` : "Lead / SRE Team"}
                    </div>
                  </div>
                </div>

                {/* Recommendation details if attached */}
                {req.recommendation && (
                  <div className="p-3 rounded bg-blue-950/10 border border-blue-500/20 space-y-1.5 text-[11px]">
                    <div className="font-bold text-blue-300 flex items-center gap-1.5">
                      <FileText className="h-3.5 w-3.5" />
                      Attached Recommendation: {req.recommendation.title}
                    </div>
                    {req.recommendation.rationale && (
                      <p className="text-muted-foreground">{req.recommendation.rationale}</p>
                    )}
                    {req.recommendation.mitigation_steps && (
                      <div className="pt-1">
                        <span className="text-[10px] text-muted-foreground uppercase font-semibold">Recommended Mitigations:</span>
                        <ul className="list-disc list-inside text-foreground pl-1 space-y-0.5 mt-0.5">
                          {req.recommendation.mitigation_steps.map((step: string, idx: number) => (
                            <li key={idx}>{step}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* Form if waiting and not expired */}
                {req.status === "WAITING_FOR_APPROVAL" && !expired ? (
                  <div className="space-y-3 pt-1">
                    <div className="space-y-1">
                      <label className="text-[10px] uppercase text-muted-foreground font-semibold flex items-center gap-1.5">
                        <Fingerprint className="h-3.5 w-3.5 text-accent" />
                        Audit Justification & Authorization Notes (Required)
                      </label>
                      <textarea
                        rows={2}
                        value={justifications[req.id] || ""}
                        onChange={(e) => setJustifications({ ...justifications, [req.id]: e.target.value })}
                        placeholder="Enter verification notes, staging smoke-test pass confirmation, or rejection rationale..."
                        className="w-full p-2.5 rounded bg-background border border-border text-foreground text-xs focus:outline-none focus:border-accent font-mono"
                      />
                    </div>

                    <div className="flex items-center justify-end gap-2 flex-wrap">
                      <button
                        onClick={() => handleDecision(req.id, "REQUEST_MORE_INFORMATION")}
                        disabled={submitting === req.id}
                        className="px-3 py-1.5 rounded bg-muted/50 border border-border text-muted-foreground hover:text-foreground text-xs font-semibold transition-colors disabled:opacity-50 flex items-center gap-1"
                      >
                        <HelpCircle className="h-3.5 w-3.5" />
                        Request Info
                      </button>
                      <button
                        onClick={() => handleDecision(req.id, "ESCALATE")}
                        disabled={submitting === req.id}
                        className="px-3 py-1.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-400 hover:bg-amber-500/20 text-xs font-semibold transition-colors disabled:opacity-50 flex items-center gap-1"
                      >
                        <AlertOctagon className="h-3.5 w-3.5" />
                        Escalate
                      </button>
                      <button
                        onClick={() => handleDecision(req.id, "REJECT")}
                        disabled={submitting === req.id}
                        className="px-3.5 py-1.5 rounded bg-rose-500/10 border border-rose-500/30 text-rose-400 hover:bg-rose-500/20 text-xs font-semibold transition-colors disabled:opacity-50"
                      >
                        Reject Action
                      </button>
                      <button
                        onClick={() => handleDecision(req.id, "APPROVE")}
                        disabled={submitting === req.id}
                        className="px-4 py-1.5 rounded bg-emerald-500 text-slate-950 font-bold hover:bg-emerald-400 transition-colors disabled:opacity-50 text-xs flex items-center gap-1"
                      >
                        <Fingerprint className="h-3.5 w-3.5" />
                        Sign & Authorize
                      </button>
                    </div>
                  </div>
                ) : expired && req.status === "WAITING_FOR_APPROVAL" ? (
                  <div className="p-3 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono flex items-center gap-2">
                    <Clock className="h-4 w-4" />
                    <span>This approval request has passed its expiration window. It has failed closed and cannot be authorized.</span>
                  </div>
                ) : (
                  /* Completed audit trail with SHA-256 fingerprint */
                  <div className="space-y-2 pt-2 border-t border-border">
                    <div className="text-[10px] uppercase text-muted-foreground font-semibold flex items-center gap-1.5">
                      <Fingerprint className="h-3.5 w-3.5 text-accent" />
                      Cryptographic Audit Signature Trail
                    </div>
                    {req.decisions?.map((d: any) => (
                      <div key={d.id} className="p-3 rounded bg-background/50 border border-border space-y-1 text-[11px]">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-foreground">
                            Decision: <span className={d.decision === "APPROVE" || d.decision === "APPROVED" ? "text-emerald-400" : "text-rose-400"}>{d.decision}</span>
                          </span>
                          <span className="text-[10px] text-muted-foreground">{formatDate(d.decided_at)}</span>
                        </div>
                        <div className="text-muted-foreground">
                          <span className="text-foreground">Audited Notes: </span>{d.justification || d.notes}
                        </div>
                        <div className="text-[10px] text-muted-foreground/80 truncate font-mono bg-background/80 p-1 rounded border border-border/50">
                          Fingerprint: {d.audit_signature}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
