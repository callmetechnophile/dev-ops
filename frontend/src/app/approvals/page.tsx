"use client";

import React, { useEffect, useState } from "react";
import { CheckCheck, XCircle, ShieldCheck, Clock, CheckCircle2, AlertTriangle, Fingerprint } from "lucide-react";
import { fetchApprovals, submitApproval } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { formatDate } from "@/lib/utils";

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<any[]>([]);
  const [justifications, setJustifications] = useState<{ [key: string]: string }>({});
  const [submitting, setSubmitting] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const load = async () => {
    try {
      const res = await fetchApprovals();
      setApprovals(res.items || []);
    } catch (err: any) {
      console.error(err);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleDecision = async (requestId: string, decision: "APPROVED" | "REJECTED") => {
    const just = (justifications[requestId] || "").trim();
    if (!just) {
      setErrorMsg("A written justification is strictly required for production deployment decisions.");
      return;
    }
    setErrorMsg(null);
    setSuccessMsg(null);
    setSubmitting(requestId);

    try {
      // Default lead engineer user ID
      const userId = "00000000-0000-0000-0000-000000000002";
      const decisionRecord = await submitApproval(requestId, decision, just, userId);
      setSuccessMsg(`Decision ${decision} recorded with SHA-256 audit signature: ${decisionRecord.audit_signature.slice(0, 16)}...`);
      await load();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to submit approval");
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <CheckCheck className="h-5 w-5 text-emerald-400" />
          Human Approval Gate & Governance
        </h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Section 9 Mandate: The agent cannot autonomously mutate production infrastructure. Every operational action requires cryptographically signed human authorization.
        </p>
      </div>

      {errorMsg && (
        <div className="p-3 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono">
          {errorMsg}
        </div>
      )}

      {successMsg && (
        <div className="p-3 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-mono">
          {successMsg}
        </div>
      )}

      <div className="space-y-4">
        {approvals.length === 0 ? (
          <div className="p-12 text-center border border-dashed border-border rounded-lg bg-card/20 space-y-2 font-mono">
            <ShieldCheck className="h-6 w-6 text-emerald-400 mx-auto" />
            <div className="text-xs text-foreground font-semibold">No Pending Approval Requests</div>
            <p className="text-[11px] text-muted-foreground max-w-md mx-auto">
              When high-risk deployments or recommended mitigations are queued, they will appear here for review and digital signature.
            </p>
          </div>
        ) : (
          approvals.map((req) => (
            <div key={req.id} className="p-5 rounded-lg bg-card border border-border space-y-4 font-mono text-xs">
              <div className="flex items-center justify-between pb-3 border-b border-border">
                <div className="space-y-0.5">
                  <div className="text-foreground font-bold text-sm">
                    {req.requested_action}
                  </div>
                  <div className="text-muted-foreground text-[10px]">
                    Request ID: {req.id} &middot; Deployment: {req.deployment_id.slice(0, 8)}... &middot; Created {formatDate(req.created_at)}
                  </div>
                </div>
                <StatusBadge status={req.status} />
              </div>

              {/* Approval form if waiting */}
              {req.status === "WAITING_FOR_APPROVAL" ? (
                <div className="space-y-3 pt-1">
                  <div className="space-y-1">
                    <label className="text-[10px] uppercase text-muted-foreground font-semibold">
                      Decision Justification (Audited)
                    </label>
                    <textarea
                      rows={2}
                      value={justifications[req.id] || ""}
                      onChange={(e) => setJustifications({ ...justifications, [req.id]: e.target.value })}
                      placeholder="Enter verification evidence, testing confirmations, or rejection reasons..."
                      className="w-full p-2.5 rounded bg-background border border-border text-foreground text-xs focus:outline-none focus:border-accent font-mono"
                    />
                  </div>

                  <div className="flex items-center justify-end gap-3">
                    <button
                      onClick={() => handleDecision(req.id, "REJECTED")}
                      disabled={submitting === req.id}
                      className="px-3.5 py-1.5 rounded bg-rose-500/10 border border-rose-500/30 text-rose-400 hover:bg-rose-500/20 font-semibold transition-colors disabled:opacity-50"
                    >
                      Reject Action
                    </button>
                    <button
                      onClick={() => handleDecision(req.id, "APPROVED")}
                      disabled={submitting === req.id}
                      className="px-4 py-1.5 rounded bg-emerald-500 text-slate-950 font-bold hover:bg-emerald-400 transition-colors disabled:opacity-50"
                    >
                      Sign & Approve
                    </button>
                  </div>
                </div>
              ) : (
                /* Completed audit trail */
                <div className="space-y-2 pt-2 border-t border-border">
                  <div className="text-[10px] uppercase text-muted-foreground font-semibold flex items-center gap-1.5">
                    <Fingerprint className="h-3.5 w-3.5 text-accent" />
                    Cryptographic Audit Trail
                  </div>
                  {req.decisions?.map((d: any) => (
                    <div key={d.id} className="p-3 rounded bg-background/50 border border-border space-y-1 text-[11px]">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-foreground">Decision: {d.decision}</span>
                        <span className="text-[10px] text-muted-foreground">{formatDate(d.decided_at)}</span>
                      </div>
                      <div className="text-muted-foreground">
                        <span className="text-foreground">Justification: </span>{d.justification}
                      </div>
                      <div className="text-[10px] text-muted-foreground truncate font-mono">
                        Signature: {d.audit_signature}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
