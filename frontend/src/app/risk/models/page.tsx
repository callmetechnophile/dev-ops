"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  BarChart3,
  CheckCircle2,
  Clock,
  Cpu,
  Database,
  History,
  Info,
  Layers,
  Play,
  RefreshCw,
  Scale,
  Shield,
  ShieldAlert,
  Sliders,
  Sparkles,
  Zap,
} from "lucide-react";
import {
  fetchModelStatus,
  fetchModels,
  fetchModelEvaluation,
  triggerModelTraining,
} from "@/lib/api";
import { formatDate } from "@/lib/utils";

export default function ModelRegistryPage() {
  const [modelStatus, setModelStatus] = useState<any | null>(null);
  const [models, setModels] = useState<any[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<string | null>(null);
  const [selectedEvaluation, setSelectedEvaluation] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [training, setTraining] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  async function loadData() {
    setLoading(true);
    try {
      const [status, registry] = await Promise.all([
        fetchModelStatus(),
        fetchModels(),
      ]);
      setModelStatus(status);
      setModels(registry || []);

      if (registry && registry.length > 0) {
        const active = registry.find((m: any) => m.status === "ACTIVE") || registry[0];
        setSelectedVersion(active.model_version);
        const evalData = await fetchModelEvaluation(active.model_version);
        setSelectedEvaluation(evalData);
      }
    } catch (err) {
      console.error("Failed to load model registry data", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function handleSelectVersion(version: string) {
    setSelectedVersion(version);
    try {
      const evalData = await fetchModelEvaluation(version);
      setSelectedEvaluation(evalData);
    } catch (err) {
      console.error("Failed to fetch evaluation for version", version, err);
    }
  }

  async function handleTrainModel() {
    setTraining(true);
    setMessage(null);
    try {
      const res = await triggerModelTraining();
      setMessage({
        text: `Training job completed: status is ${res.status}. ${res.message || ""}`,
        type: res.status === "FAILED" ? "error" : "success",
      });
      await loadData();
    } catch (err: any) {
      setMessage({
        text: err.message || "Failed to trigger model training.",
        type: "error",
      });
    } finally {
      setTraining(false);
    }
  }

  const isModelActive = modelStatus?.status === "ACTIVE";

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      {/* Breadcrumb & Navigation */}
      <div className="flex items-center justify-between">
        <Link
          href="/risk"
          className="inline-flex items-center gap-2 text-sm text-slate-400 transition-colors hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Risk Center
        </Link>

        <button
          onClick={handleTrainModel}
          disabled={training}
          className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors shadow-lg shadow-indigo-600/20"
        >
          {training ? (
            <>
              <RefreshCw className="h-4 w-4 animate-spin" />
              Training ML Pipeline...
            </>
          ) : (
            <>
              <Play className="h-4 w-4" />
              Retrain Model Pipeline
            </>
          )}
        </button>
      </div>

      {/* Alert Banner if training resulted in message */}
      {message && (
        <div
          className={`flex items-start gap-3 rounded-xl border p-4 text-sm ${
            message.type === "success"
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              : "border-rose-500/30 bg-rose-500/10 text-rose-300"
          }`}
        >
          {message.type === "success" ? (
            <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-400" />
          ) : (
            <AlertCircle className="h-5 w-5 shrink-0 text-rose-400" />
          )}
          <div className="flex-1">
            <p className="font-medium">{message.text}</p>
          </div>
        </div>
      )}

      {/* Model State & Eligibility Card */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-6">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <span
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${
                  isModelActive
                    ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/30"
                    : "text-amber-400 bg-amber-500/10 border-amber-500/30"
                }`}
              >
                <Cpu className="h-3.5 w-3.5" />
                {isModelActive ? "ACTIVE ML MODEL" : "INSUFFICIENT HISTORICAL DATA"}
              </span>
              <span className="font-mono text-xs text-slate-400">
                Active Version: {modelStatus?.active_model_version || "Deterministic Rules v1.0"}
              </span>
            </div>

            <h1 className="text-2xl font-bold tracking-tight text-white">
              Model Registry & Probability Calibration
            </h1>

            <p className="text-sm text-slate-400 max-w-2xl">
              {isModelActive
                ? "Calibrated XGBoost classifier trained on chronological deployment splits with Platt scaling probability calibration."
                : "The system enforces strict data governance: failure probabilities are never fabricated. A deterministic rule baseline is active until at least 30 labeled deployments with minority-class representation exist."}
            </p>
          </div>

          {/* Dataset Quality & Eligibility Checklist */}
          <div className="rounded-xl border border-slate-800 bg-slate-800/40 p-4 shrink-0 min-w-[280px] space-y-3">
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Database className="h-3.5 w-3.5 text-indigo-400" />
              Eligibility Checklist
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-300">Total Labeled Deployments:</span>
                <span className="font-mono font-semibold text-white">
                  {modelStatus?.labeled_deployments_count || 0} / 30 required
                </span>
              </div>
              <div className="h-1.5 w-full bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-500 transition-all"
                  style={{
                    width: `${Math.min(100, ((modelStatus?.labeled_deployments_count || 0) / 30) * 100)}%`,
                  }}
                />
              </div>

              <div className="flex items-center justify-between pt-1">
                <span className="text-slate-300">Minority Class Samples:</span>
                <span className="font-mono font-semibold text-white">
                  {modelStatus?.minority_class_count || 0} / 5 required
                </span>
              </div>
              <div className="h-1.5 w-full bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-500 transition-all"
                  style={{
                    width: `${Math.min(100, ((modelStatus?.minority_class_count || 0) / 5) * 100)}%`,
                  }}
                />
              </div>

              <div className="flex items-center justify-between pt-1">
                <span className="text-slate-300">Temporal Splitting:</span>
                <span className="font-mono text-emerald-400 font-semibold">Strict Chronological</span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-slate-300">Calibration Method:</span>
                <span className="font-mono text-indigo-300 font-semibold">Platt Scaling</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Evaluation Metrics Cards (if model evaluation available) */}
      {selectedEvaluation && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-indigo-400" />
              Evaluation Metrics for {selectedVersion}
            </h2>
            <span className="text-xs text-slate-400 font-mono">
              Evaluated on Test Split (Chronological, Zero Leakage)
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <span className="text-xs text-slate-400 font-medium">ROC-AUC</span>
              <p className="text-2xl font-bold text-white mt-1">
                {selectedEvaluation.roc_auc !== undefined ? selectedEvaluation.roc_auc.toFixed(3) : "N/A"}
              </p>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <span className="text-xs text-slate-400 font-medium">PR-AUC</span>
              <p className="text-2xl font-bold text-white mt-1">
                {selectedEvaluation.pr_auc !== undefined ? selectedEvaluation.pr_auc.toFixed(3) : "N/A"}
              </p>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <span className="text-xs text-slate-400 font-medium">Brier Score</span>
              <p className="text-2xl font-bold text-indigo-400 mt-1">
                {selectedEvaluation.brier_score !== undefined ? selectedEvaluation.brier_score.toFixed(3) : "N/A"}
              </p>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <span className="text-xs text-slate-400 font-medium">Precision</span>
              <p className="text-2xl font-bold text-white mt-1">
                {selectedEvaluation.precision !== undefined ? selectedEvaluation.precision.toFixed(3) : "N/A"}
              </p>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <span className="text-xs text-slate-400 font-medium">Recall</span>
              <p className="text-2xl font-bold text-white mt-1">
                {selectedEvaluation.recall !== undefined ? selectedEvaluation.recall.toFixed(3) : "N/A"}
              </p>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <span className="text-xs text-slate-400 font-medium">F1 Score</span>
              <p className="text-2xl font-bold text-white mt-1">
                {selectedEvaluation.f1_score !== undefined ? selectedEvaluation.f1_score.toFixed(3) : "N/A"}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Model Registry Version History Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden backdrop-blur-sm">
        <div className="border-b border-slate-800 p-5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <History className="h-5 w-5 text-indigo-400" />
            <h3 className="text-base font-semibold text-white">Model Version Registry</h3>
          </div>
          <span className="text-xs text-slate-400">
            {models.length} registered version(s)
          </span>
        </div>

        {models.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-800/50 text-xs uppercase text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="px-6 py-3">Version</th>
                  <th className="px-6 py-3">Algorithm</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3">Dataset Size</th>
                  <th className="px-6 py-3">Calibration</th>
                  <th className="px-6 py-3">Created</th>
                  <th className="px-6 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {models.map((m: any, idx: number) => (
                  <tr
                    key={idx}
                    className={`hover:bg-slate-800/30 transition-colors ${
                      selectedVersion === m.model_version ? "bg-indigo-500/5" : ""
                    }`}
                  >
                    <td className="px-6 py-4 font-mono font-medium text-white flex items-center gap-2">
                      <Cpu className="h-4 w-4 text-indigo-400" />
                      {m.model_version}
                    </td>
                    <td className="px-6 py-4 font-mono text-xs text-slate-300">
                      {m.algorithm || "XGBClassifier"}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          m.status === "ACTIVE"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                            : "bg-slate-800 text-slate-400 border border-slate-700"
                        }`}
                      >
                        {m.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-xs text-slate-300 font-mono">
                      {m.training_samples || 0} samples
                    </td>
                    <td className="px-6 py-4 text-xs text-slate-400 font-mono">
                      {m.calibration_method || "Platt Scaling"}
                    </td>
                    <td className="px-6 py-4 text-xs text-slate-400">
                      {formatDate(m.created_at)}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => handleSelectVersion(m.model_version)}
                        className={`text-xs font-medium px-3 py-1 rounded transition-colors ${
                          selectedVersion === m.model_version
                            ? "bg-indigo-600 text-white"
                            : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                        }`}
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center text-slate-400">
            <Cpu className="mx-auto h-10 w-10 text-slate-600 mb-3" />
            <p className="text-sm">No trained ML models registered yet.</p>
            <p className="text-xs text-slate-500 mt-1">
              Deterministic rules v1.0 provide baseline operational risk assessment until sample thresholds are met.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
