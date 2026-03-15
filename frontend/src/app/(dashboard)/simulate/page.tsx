"use client";

import { useEffect, useState } from "react";
import { listJobs, getJobResult } from "@/lib/api";
import type { ApprovalPrediction, ComplianceReport, AnalysisResult } from "@/lib/api";
import { TrendingUp, AlertTriangle, CheckCircle, ArrowRight, Loader2 } from "lucide-react";

// ── Sub-components ────────────────────────────────────────────────────────

function ApprovalGauge({ probability, regulator }: { probability: number; regulator: string }) {
  const color = probability >= 85 ? "#22c55e" : probability >= 65 ? "#eab308" : "#ef4444";
  const circumference = 2 * Math.PI * 40;
  const dash = (probability / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-28 h-28">
        <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
          <circle cx="50" cy="50" r="40" fill="none" stroke="#1f2937" strokeWidth="10" />
          <circle
            cx="50" cy="50" r="40" fill="none"
            stroke={color} strokeWidth="10"
            strokeDasharray={`${dash} ${circumference - dash}`}
            strokeLinecap="round"
            style={{ transition: "stroke-dasharray 1s ease" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center rotate-90">
          <span className="text-2xl font-bold text-white">{probability.toFixed(0)}%</span>
        </div>
      </div>
      <span className="text-xs text-gray-400 font-medium">{regulator}</span>
    </div>
  );
}

function ReadinessBar({ score }: { score: number }) {
  const color = score >= 85 ? "bg-green-500" : score >= 65 ? "bg-yellow-500" : "bg-red-500";
  const label = score >= 85 ? "Ready to submit" : score >= 65 ? "Needs minor fixes" : "Major issues";
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-400">Submission Readiness</span>
        <span className="text-white font-semibold">{score.toFixed(0)} / 100 — {label}</span>
      </div>
      <div className="progress-bar">
        <div className={`progress-fill ${color}`} style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

function BlockingIssues({ issues }: { issues: string[] }) {
  if (issues.length === 0) return (
    <div className="flex items-center gap-2 text-green-400 text-sm">
      <CheckCircle size={16} />
      No blocking issues — design is submission-ready
    </div>
  );
  return (
    <div className="space-y-2">
      {issues.map((issue, i) => (
        <div key={i} className="flex items-start gap-2 text-sm text-red-300">
          <AlertTriangle size={14} className="text-red-400 shrink-0 mt-0.5" />
          {issue}
        </div>
      ))}
    </div>
  );
}

function RecommendedActions({ actions }: { actions: string[] }) {
  return (
    <div className="space-y-2">
      {actions.map((action, i) => (
        <div key={i} className="flex items-start gap-2 text-sm text-gray-300">
          <ArrowRight size={14} className="text-blue-400 shrink-0 mt-0.5" />
          {action}
        </div>
      ))}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────

export default function SimulatePage() {
  const [jobs, setJobs] = useState<Array<{ job_id: string; project_id: string; filename: string | null }>>([]);
  const [selectedJob, setSelectedJob] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listJobs(20).then(({ jobs }) => {
      setJobs(jobs.filter((j) => j.status === "completed"));
    }).catch(() => {});
  }, []);

  const loadResult = async (jobId: string) => {
    setLoading(true);
    setError(null);
    setSelectedJob(jobId);
    try {
      const r = await getJobResult(jobId);
      setResult(r);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const pred = result?.prediction;
  const compliance = result?.compliance_report;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-center gap-3 mb-2">
        <TrendingUp size={24} className="text-green-400" />
        <h1 className="text-2xl font-bold text-white">Pre-Submission Approval Simulator</h1>
      </div>
      <p className="text-gray-400 text-sm mb-8">
        Predicts regulatory approval probability before you submit — preventing million-dollar redesign mistakes.
      </p>

      {/* Job selector */}
      <div className="card mb-6">
        <label className="block text-gray-400 text-xs font-medium uppercase tracking-wider mb-2">
          Select Analyzed Project
        </label>
        {jobs.length === 0 ? (
          <p className="text-gray-500 text-sm">No completed analyses found. <a href="/upload" className="text-blue-400 hover:underline">Upload a blueprint first.</a></p>
        ) : (
          <select
            value={selectedJob ?? ""}
            onChange={(e) => e.target.value && loadResult(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500"
          >
            <option value="">Choose a project...</option>
            {jobs.map((j) => (
              <option key={j.job_id} value={j.job_id}>
                {j.filename ?? j.project_id} — Job {j.job_id.slice(0, 8)}
              </option>
            ))}
          </select>
        )}
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-gray-400 py-8">
          <Loader2 size={20} className="animate-spin" />
          Loading simulation results...
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-950/40 border border-red-800 rounded-xl text-red-400 text-sm">
          {error}
        </div>
      )}

      {pred && compliance && !loading && (
        <div className="space-y-6">
          {/* Readiness score */}
          <div className="card">
            <h2 className="text-white font-semibold mb-4">Submission Readiness</h2>
            <ReadinessBar score={pred.submission_readiness_score} />
            <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
              <div>
                <div className="text-2xl font-bold text-red-400">{compliance.critical_violations}</div>
                <div className="text-xs text-gray-500">Critical</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-orange-400">{compliance.high_violations}</div>
                <div className="text-xs text-gray-500">High</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-white">
                  ${pred.estimated_rework_cost_usd.toLocaleString()}
                </div>
                <div className="text-xs text-gray-500">Est. Rework Cost</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-white">{pred.estimated_rework_days}d</div>
                <div className="text-xs text-gray-500">Est. Rework Time</div>
              </div>
            </div>
          </div>

          {/* Approval probability gauges */}
          <div className="card">
            <h2 className="text-white font-semibold mb-6">Approval Probability by Regulator</h2>
            <div className="flex flex-wrap justify-around gap-6">
              {pred.regulator_predictions.map((rp) => (
                <div key={rp.regulator} className="text-center">
                  <ApprovalGauge probability={rp.approval_probability} regulator={rp.regulator} />
                  <div className="mt-2 text-xs text-gray-500">~{rp.expected_review_days}d review</div>
                </div>
              ))}
            </div>
          </div>

          {/* Blocking issues + actions */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="card">
              <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
                <AlertTriangle size={16} className="text-red-400" />
                Blocking Issues
              </h2>
              <BlockingIssues issues={pred.top_blocking_issues} />
            </div>
            <div className="card">
              <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
                <ArrowRight size={16} className="text-blue-400" />
                Recommended Actions
              </h2>
              <RecommendedActions actions={pred.recommended_actions} />
            </div>
          </div>

          {/* Compliance summary */}
          {compliance.summary && (
            <div className="card">
              <h2 className="text-white font-semibold mb-3">AI Compliance Summary</h2>
              <p className="text-gray-300 text-sm leading-relaxed">{compliance.summary}</p>
              <div className="mt-2 text-xs text-gray-600">
                Model: {pred.model_version} · Confidence: {(pred.confidence * 100).toFixed(0)}%
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
