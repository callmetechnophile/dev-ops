"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Activity,
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  Compass,
  FileCode,
  Flame,
  HelpCircle,
  History,
  Layers,
  Lightbulb,
  Plus,
  RefreshCw,
  RotateCcw,
  Shield,
  ShieldAlert,
  Terminal,
  XCircle,
} from "lucide-react";
import {
  fetchIncident,
  fetchIncidentTimeline,
  fetchIncidentClassifications,
  fetchIncidentHypotheses,
  fetchSimilarIncidents,
  fetchIncidentRemediations,
  confirmHypothesis,
  rejectHypothesis,
  markInsufficientEvidence,
  recordIncidentRemediation,
} from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { formatDate } from "@/lib/utils";

export default function IncidentDetailPage() {
  const params = useParams();
  const id = params?.id as string;

  const [incident, setIncident] = useState<any | null>(null);
  const [timeline, setTimeline] = useState<any | null>(null);
  const [classifications, setClassifications] = useState<any[]>([]);
  const [hypotheses, setHypotheses] = useState<any[]>([]);
  const [similarIncidents, setSimilarIncidents] = useState<any[]>([]);
  const [remediations, setRemediations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"timeline" | "hypotheses" | "similar" | "remediations">("hypotheses");

  // Confirmation Modal State
  const [confirmModalHypothesis, setConfirmModalHypothesis] = useState<any | null>(null);
  const [engineerName, setEngineerName] = useState<string>("SRE Engineer");
  const [confirmationNotes, setConfirmationNotes] = useState<string>("");
  const [rootCauseSummary, setRootCauseSummary] = useState<string>("");
  const [engineeringLesson, setEngineeringLesson] = useState<string>("");
  const [preventionStrategy, setPreventionStrategy] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // New Remediation Modal State
  const [showRemediationModal, setShowRemediationModal] = useState<boolean>(false);
  const [remActionType, setRemActionType] = useState<string>("ROLLBACK");
  const [remDescription, setRemDescription] = useState<string>("");
  const [remOutcome, setRemOutcome] = useState<string>("SUCCESS");
  const [remEffectiveness, setRemEffectiveness] = useState<string>("HIGH");

  async function loadAllData() {
    if (!id) return;
    try {
      setLoading(true);
      const [inc, tl, cls, hyps, sim, rems] = await Promise.all([
        fetchIncident(id),
        fetchIncidentTimeline(id),
        fetchIncidentClassifications(id),
        fetchIncidentHypotheses(id),
        fetchSimilarIncidents(id),
        fetchIncidentRemediations(id),
      ]);
      setIncident(inc);
      setTimeline(tl);
      setClassifications(cls);
      setHypotheses(hyps);
      setSimilarIncidents(sim);
      setRemediations(rems);
    } catch (e: any) {
      console.error("Failed to load incident detail:", e);
      setActionError(e.message || "Failed to load incident");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAllData();
  }, [id]);

  const handleOpenConfirmModal = (hyp: any) => {
    setConfirmModalHypothesis(hyp);
    setRootCauseSummary(hyp.hypothesis);
    setEngineeringLesson(hyp.explanation || "Verify configuration and resource boundaries before production deployment.");
    setPreventionStrategy("Add automated pre-flight assertion check to CI pipeline.");
    setConfirmationNotes("Verified via production pod diagnostics and error logs.");
    setActionError(null);
  };

  const handleConfirmSubmit = async () => {
    if (!confirmModalHypothesis || !id) return;
    setIsSubmitting(true);
    setActionError(null);
    try {
      await confirmHypothesis(id, confirmModalHypothesis.id, {
        confirmed_by: engineerName,
        confirmation_notes: confirmationNotes,
        root_cause_summary: rootCauseSummary,
        verified_engineering_lesson: engineeringLesson,
        prevention_strategy: preventionStrategy,
      });
      setConfirmModalHypothesis(null);
      await loadAllData();
    } catch (err: any) {
      setActionError(err.message || "Failed to confirm hypothesis");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReject = async (hypId: string) => {
    const reason = window.prompt("Reason for rejecting hypothesis:", "Evidence does not correlate with primary failure mechanism");
    if (!reason) return;
    try {
      await rejectHypothesis(id, hypId, {
        rejected_by: engineerName,
        rejection_reason: reason,
      });
      await loadAllData();
    } catch (err: any) {
      alert(err.message || "Failed to reject hypothesis");
    }
  };

  const handleInsufficientEvidence = async (hypId: string) => {
    const notes = window.prompt("Diagnostic notes for insufficient evidence:", "Missing container stdout and telemetry logs");
    if (notes === null) return;
    try {
      await markInsufficientEvidence(id, hypId, {
        reviewed_by: engineerName,
        notes: notes,
      });
      await loadAllData();
    } catch (err: any) {
      alert(err.message || "Failed to update hypothesis");
    }
  };

  const handleRecordRemediation = async () => {
    if (!id || !remDescription) return;
    setIsSubmitting(true);
    try {
      await recordIncidentRemediation(id, {
        action_type: remActionType,
        description: remDescription,
        proposed_by: engineerName,
        execution_status: "EXECUTED",
        outcome: remOutcome,
        effectiveness: remEffectiveness,
      });
      setShowRemediationModal(false);
      setRemDescription("");
      await loadAllData();
    } catch (err: any) {
      alert(err.message || "Failed to record remediation");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="p-16 text-center text-xs font-mono text-muted-foreground">
        Loading operational incident memory & reconstruction...
      </div>
    );
  }

  if (!incident) {
    return (
      <div className="p-16 text-center space-y-4">
        <AlertCircle className="h-8 w-8 text-rose-500 mx-auto" />
        <div className="text-sm font-mono text-foreground font-semibold">Incident Not Found</div>
        <Link href="/incidents" className="text-xs font-mono text-rose-400 hover:underline">
          Return to Incident Intelligence Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Back Button and Title */}
      <div className="space-y-3">
        <Link
          href="/incidents"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Incidents</span>
        </Link>

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-sm font-bold text-rose-400 bg-rose-500/10 border border-rose-500/30 px-2 py-0.5 rounded">
                {incident.incident_key}
              </span>
              <span
                className={`text-xs font-mono px-2 py-0.5 rounded border uppercase font-bold ${
                  incident.severity === "P1"
                    ? "bg-rose-500/20 text-rose-300 border-rose-500/30"
                    : "bg-amber-500/20 text-amber-300 border-amber-500/30"
                }`}
              >
                {incident.severity}
              </span>
              <StatusBadge status={incident.status} />
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-secondary text-secondary-foreground uppercase">
                {incident.environment}
              </span>
              <span className="text-xs font-mono text-muted-foreground border border-border px-2 py-0.5 rounded">
                {incident.incident_type}
              </span>
            </div>
            <h1 className="text-xl font-bold tracking-tight text-foreground">{incident.title}</h1>
            <p className="text-xs text-muted-foreground">{incident.summary}</p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowRemediationModal(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-border bg-secondary/60 hover:bg-secondary text-foreground text-xs font-mono transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Record Remediation</span>
            </button>
            <button
              onClick={loadAllData}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-border bg-secondary/30 hover:bg-secondary text-muted-foreground hover:text-foreground text-xs font-mono transition-colors"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Confirmed Root Cause Banner */}
      {incident.confirmed_root_cause && (
        <div className="p-4 rounded border border-cyan-500/30 bg-cyan-950/20 space-y-2">
          <div className="flex items-center justify-between text-xs font-mono text-cyan-400 font-semibold">
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4" />
              CONFIRMED ROOT CAUSE & VERIFIED ENGINEERING LESSON
            </span>
            <span>Confirmed by: {incident.confirmed_root_cause.confirmed_by}</span>
          </div>
          <div className="text-xs font-mono text-foreground font-semibold">
            {incident.confirmed_root_cause.root_cause_summary}
          </div>
          <div className="text-xs text-muted-foreground">
            <span className="text-cyan-300 font-semibold font-mono">Lesson: </span>
            {incident.confirmed_root_cause.verified_engineering_lesson}
          </div>
          <div className="text-xs text-muted-foreground">
            <span className="text-cyan-300 font-semibold font-mono">Prevention: </span>
            {incident.confirmed_root_cause.prevention_strategy}
          </div>
        </div>
      )}

      {/* Failure Classifications Grid */}
      {classifications.length > 0 && (
        <div className="p-4 rounded border border-border bg-card/40 space-y-3">
          <div className="text-xs font-mono text-muted-foreground uppercase font-semibold flex items-center gap-1.5">
            <Terminal className="h-3.5 w-3.5 text-rose-400" />
            Deterministic Failure Classifications ({classifications.length})
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {classifications.map((fc) => (
              <div key={fc.id} className="p-3 rounded border border-border bg-secondary/30 space-y-2">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-rose-400 font-semibold">{fc.category}</span>
                  <span className="text-muted-foreground text-[10px]">Method: {fc.classification_method}</span>
                </div>
                <div className="text-xs font-mono text-foreground font-semibold">{fc.subcategory}</div>
                {fc.evidence && Object.keys(fc.evidence).length > 0 && (
                  <div className="p-2 rounded bg-black/40 border border-border/50 text-[11px] font-mono text-muted-foreground overflow-x-auto max-h-32">
                    <pre>{JSON.stringify(fc.evidence, null, 2)}</pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex border-b border-border text-xs font-mono">
        <button
          onClick={() => setActiveTab("hypotheses")}
          className={`px-4 py-2 font-semibold border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === "hypotheses"
              ? "border-rose-500 text-rose-400"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Lightbulb className="h-4 w-4" />
          <span>Root-Cause Hypotheses ({hypotheses.length})</span>
        </button>

        <button
          onClick={() => setActiveTab("timeline")}
          className={`px-4 py-2 font-semibold border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === "timeline"
              ? "border-rose-500 text-rose-400"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Clock className="h-4 w-4" />
          <span>Chronological Timeline ({timeline?.entry_count || 0})</span>
        </button>

        <button
          onClick={() => setActiveTab("similar")}
          className={`px-4 py-2 font-semibold border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === "similar"
              ? "border-rose-500 text-rose-400"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Compass className="h-4 w-4" />
          <span>Similar Historical Incidents ({similarIncidents.length})</span>
        </button>

        <button
          onClick={() => setActiveTab("remediations")}
          className={`px-4 py-2 font-semibold border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === "remediations"
              ? "border-rose-500 text-rose-400"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <RotateCcw className="h-4 w-4" />
          <span>Remediation Records ({remediations.length})</span>
        </button>
      </div>

      {/* Tab 1: Root-Cause Hypotheses & Human Verification */}
      {activeTab === "hypotheses" && (
        <div className="space-y-4">
          {hypotheses.length === 0 ? (
            <div className="p-12 text-center text-xs font-mono text-muted-foreground border border-dashed border-border rounded">
              No hypotheses generated yet. Deterministic rule analysis is ready.
            </div>
          ) : (
            hypotheses.map((h) => (
              <div
                key={h.id}
                className={`p-4 rounded border transition-all space-y-3 ${
                  h.status === "CONFIRMED"
                    ? "border-cyan-500/40 bg-cyan-950/10"
                    : h.status === "REJECTED"
                    ? "border-border/60 bg-secondary/20 opacity-60"
                    : "border-border bg-card/60"
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className={`text-xs font-mono px-2 py-0.5 rounded font-bold uppercase ${
                        h.status === "CONFIRMED"
                          ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                          : h.status === "REJECTED"
                          ? "bg-red-500/20 text-red-300 border border-red-500/30"
                          : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                      }`}
                    >
                      {h.status}
                    </span>

                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-secondary text-muted-foreground border border-border">
                      Confidence: {h.confidence_level}
                    </span>

                    <span className="text-[10px] font-mono text-muted-foreground">
                      Generated by: {h.generated_by}
                    </span>
                  </div>

                  {/* Human Verification Action Buttons */}
                  {h.status !== "CONFIRMED" && (
                    <div className="flex items-center gap-2 pt-2 sm:pt-0">
                      <button
                        onClick={() => handleOpenConfirmModal(h)}
                        className="inline-flex items-center gap-1 px-3 py-1 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30 text-xs font-mono rounded transition-colors"
                      >
                        <CheckCircle2 className="h-3 w-3" />
                        <span>Confirm Root Cause</span>
                      </button>

                      <button
                        onClick={() => handleReject(h.id)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 bg-red-500/10 hover:bg-red-500/20 text-red-300 border border-red-500/20 text-xs font-mono rounded transition-colors"
                      >
                        <XCircle className="h-3 w-3" />
                        <span>Reject</span>
                      </button>

                      <button
                        onClick={() => handleInsufficientEvidence(h.id)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 bg-secondary hover:bg-secondary/80 text-muted-foreground text-xs font-mono rounded border border-border transition-colors"
                      >
                        <HelpCircle className="h-3 w-3" />
                        <span>Insufficient Evidence</span>
                      </button>
                    </div>
                  )}
                </div>

                <div className="text-sm font-mono text-foreground font-semibold">{h.hypothesis}</div>
                <p className="text-xs text-muted-foreground leading-relaxed">{h.explanation}</p>

                {h.evidence_event_ids && h.evidence_event_ids.length > 0 && (
                  <div className="flex items-center gap-2 text-[11px] font-mono text-muted-foreground pt-1">
                    <span className="font-semibold text-foreground">Verified Supporting Evidence IDs:</span>
                    {h.evidence_event_ids.map((eid: string) => (
                      <span key={eid} className="px-1.5 py-0.5 rounded bg-secondary border border-border">
                        {eid.slice(0, 8)}...
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab 2: Chronological Timeline */}
      {activeTab === "timeline" && (
        <div className="space-y-4">
          {timeline?.entries && timeline.entries.length > 0 ? (
            <div className="relative border-l border-border/80 ml-4 space-y-6 py-2">
              {timeline.entries.map((entry: any) => (
                <div key={entry.id} className="relative pl-6">
                  <div className="absolute -left-1.5 top-1.5 h-3 w-3 rounded-full bg-secondary border-2 border-rose-500" />
                  <div className="p-3 rounded border border-border bg-card/60 space-y-1">
                    <div className="flex items-center justify-between text-xs font-mono">
                      <span className="font-bold text-foreground">{entry.title}</span>
                      <span className="text-muted-foreground">{formatDate(entry.occurred_at)}</span>
                    </div>
                    <p className="text-xs text-muted-foreground">{entry.description}</p>
                    <div className="flex items-center gap-3 text-[10px] font-mono text-muted-foreground pt-1">
                      <span>Type: {entry.event_type}</span>
                      <span>Source: {entry.source}</span>
                      <span className="uppercase text-rose-400">Relation: {entry.relationship_type}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-12 text-center text-xs font-mono text-muted-foreground border border-dashed border-border rounded">
              No chronological events attached to this incident timeline yet.
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Similar Historical Incidents */}
      {activeTab === "similar" && (
        <div className="space-y-4">
          {similarIncidents.length === 0 ? (
            <div className="p-12 text-center text-xs font-mono text-muted-foreground border border-dashed border-border rounded">
              No historically similar incidents found in operational memory.
            </div>
          ) : (
            similarIncidents.map((sim) => (
              <div key={sim.incident_id} className="p-4 rounded border border-border bg-card/60 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-rose-400">{sim.incident_key}</span>
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-secondary text-secondary-foreground">
                      Similarity: {Math.round(sim.similarity_score * 100)}%
                    </span>
                    <span className="text-xs font-mono text-muted-foreground">({sim.environment})</span>
                  </div>
                  <Link
                    href={`/incidents/${sim.incident_id}`}
                    className="text-xs font-mono text-rose-400 hover:underline"
                  >
                    View Details →
                  </Link>
                </div>
                <div className="text-xs font-semibold text-foreground">{sim.title}</div>
                {sim.confirmed_root_cause_summary && (
                  <div className="text-xs text-cyan-300 font-mono bg-cyan-950/20 p-2 rounded border border-cyan-500/20">
                    <span className="font-bold">Historical Cause: </span>
                    {sim.confirmed_root_cause_summary}
                  </div>
                )}
                {sim.verified_engineering_lesson && (
                  <div className="text-xs text-muted-foreground">
                    <span className="font-bold font-mono text-foreground">Verified Lesson: </span>
                    {sim.verified_engineering_lesson}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab 4: Remediation Records */}
      {activeTab === "remediations" && (
        <div className="space-y-4">
          {remediations.length === 0 ? (
            <div className="p-12 text-center text-xs font-mono text-muted-foreground border border-dashed border-border rounded">
              No historical remediation actions recorded for this incident.
            </div>
          ) : (
            remediations.map((rem) => (
              <div key={rem.id} className="p-4 rounded border border-border bg-card/60 space-y-2">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-rose-400 font-bold uppercase">{rem.action_type}</span>
                  <span className="text-muted-foreground">Status: {rem.execution_status}</span>
                </div>
                <div className="text-xs text-foreground font-mono">{rem.description}</div>
                <div className="flex items-center gap-4 text-[11px] font-mono text-muted-foreground pt-1">
                  <span>Outcome: {rem.outcome || "UNKNOWN"}</span>
                  <span>Effectiveness: {rem.effectiveness || "MEDIUM"}</span>
                  <span>Proposed by: {rem.proposed_by}</span>
                  <span>Recorded: {formatDate(rem.created_at)}</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Confirmation Modal */}
      {confirmModalHypothesis && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-lg max-w-lg w-full p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold font-mono text-foreground flex items-center gap-2">
                <Shield className="h-4 w-4 text-emerald-400" />
                Human Engineering Verification
              </h3>
              <button
                onClick={() => setConfirmModalHypothesis(null)}
                className="text-xs font-mono text-muted-foreground hover:text-foreground"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-muted-foreground">
              Confirming a root cause requires explicit human verification. This action creates a permanent engineering lesson in operational memory for future predictive risk models.
            </p>

            {actionError && (
              <div className="p-3 rounded bg-red-950/40 border border-red-500/30 text-xs font-mono text-red-300">
                {actionError}
              </div>
            )}

            <div className="space-y-3 text-xs font-mono">
              <div className="space-y-1">
                <label className="text-muted-foreground">VERIFYING ENGINEER IDENTITY:</label>
                <input
                  type="text"
                  value={engineerName}
                  onChange={(e) => setEngineerName(e.target.value)}
                  className="w-full bg-secondary/60 border border-border rounded px-3 py-1.5 text-foreground focus:outline-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-muted-foreground">ROOT CAUSE SUMMARY:</label>
                <textarea
                  rows={2}
                  value={rootCauseSummary}
                  onChange={(e) => setRootCauseSummary(e.target.value)}
                  className="w-full bg-secondary/60 border border-border rounded px-3 py-1.5 text-foreground focus:outline-none resize-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-muted-foreground">VERIFIED ENGINEERING LESSON:</label>
                <textarea
                  rows={3}
                  value={engineeringLesson}
                  onChange={(e) => setEngineeringLesson(e.target.value)}
                  className="w-full bg-secondary/60 border border-border rounded px-3 py-1.5 text-foreground focus:outline-none resize-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-muted-foreground">PREVENTION STRATEGY:</label>
                <textarea
                  rows={2}
                  value={preventionStrategy}
                  onChange={(e) => setPreventionStrategy(e.target.value)}
                  className="w-full bg-secondary/60 border border-border rounded px-3 py-1.5 text-foreground focus:outline-none resize-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-muted-foreground">CONFIRMATION NOTES / AUDIT EVIDENCE:</label>
                <input
                  type="text"
                  value={confirmationNotes}
                  onChange={(e) => setConfirmationNotes(e.target.value)}
                  className="w-full bg-secondary/60 border border-border rounded px-3 py-1.5 text-foreground focus:outline-none"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setConfirmModalHypothesis(null)}
                className="px-4 py-2 text-xs font-mono rounded border border-border bg-secondary hover:bg-secondary/80 text-foreground"
              >
                Cancel
              </button>
              <button
                disabled={isSubmitting || !rootCauseSummary || !engineeringLesson}
                onClick={handleConfirmSubmit}
                className="px-4 py-2 text-xs font-mono font-semibold rounded bg-emerald-500 hover:bg-emerald-600 text-black disabled:opacity-50 transition-colors"
              >
                {isSubmitting ? "Confirming..." : "Confirm & Save Lesson"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Record Remediation Modal */}
      {showRemediationModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-lg max-w-md w-full p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold font-mono text-foreground">Record Remediation Action</h3>
              <button
                onClick={() => setShowRemediationModal(false)}
                className="text-xs font-mono text-muted-foreground hover:text-foreground"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs font-mono">
              <div className="space-y-1">
                <label className="text-muted-foreground">ACTION TYPE:</label>
                <select
                  value={remActionType}
                  onChange={(e) => setRemActionType(e.target.value)}
                  className="w-full bg-secondary/60 border border-border rounded px-3 py-1.5 text-foreground focus:outline-none"
                >
                  <option value="ROLLBACK">ROLLBACK</option>
                  <option value="CONFIG_PATCH">CONFIG_PATCH</option>
                  <option value="RESTART">POD_RESTART</option>
                  <option value="DEPENDENCY_PIN">DEPENDENCY_PIN</option>
                  <option value="RESOURCE_QUOTA_BUMP">RESOURCE_QUOTA_BUMP</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-muted-foreground">ACTION DESCRIPTION:</label>
                <textarea
                  rows={3}
                  value={remDescription}
                  onChange={(e) => setRemDescription(e.target.value)}
                  placeholder="e.g. Rolled back deployment to previous stable SHA 3f4a9b"
                  className="w-full bg-secondary/60 border border-border rounded px-3 py-1.5 text-foreground focus:outline-none resize-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <label className="text-muted-foreground">OUTCOME:</label>
                  <select
                    value={remOutcome}
                    onChange={(e) => setRemOutcome(e.target.value)}
                    className="w-full bg-secondary/60 border border-border rounded px-3 py-1.5 text-foreground focus:outline-none"
                  >
                    <option value="SUCCESS">SUCCESS</option>
                    <option value="PARTIAL_SUCCESS">PARTIAL_SUCCESS</option>
                    <option value="FAILED">FAILED</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-muted-foreground">EFFECTIVENESS:</label>
                  <select
                    value={remEffectiveness}
                    onChange={(e) => setRemEffectiveness(e.target.value)}
                    className="w-full bg-secondary/60 border border-border rounded px-3 py-1.5 text-foreground focus:outline-none"
                  >
                    <option value="HIGH">HIGH</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="LOW">LOW</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowRemediationModal(false)}
                className="px-4 py-2 text-xs font-mono rounded border border-border bg-secondary hover:bg-secondary/80 text-foreground"
              >
                Cancel
              </button>
              <button
                disabled={isSubmitting || !remDescription}
                onClick={handleRecordRemediation}
                className="px-4 py-2 text-xs font-mono font-semibold rounded bg-rose-500 hover:bg-rose-600 text-white disabled:opacity-50 transition-colors"
              >
                {isSubmitting ? "Recording..." : "Save Remediation"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
