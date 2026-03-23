"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getProject } from "@/lib/api";
import type { Project } from "@/lib/api";
import {
  ArrowLeft,
  ExternalLink,
  CheckCircle,
  AlertTriangle,
  Clock,
  DollarSign,
  AlertCircle,
  BarChart2,
} from "lucide-react";

const RISK_COLOR: Record<string, string> = {
  low: "text-green-400",
  medium: "text-yellow-400",
  high: "text-orange-400",
  very_high: "text-red-400",
};

function deriveRiskTier(score: number | null | undefined): string {
  if (score == null) return "unknown";
  if (score >= 85) return "low";
  if (score >= 65) return "medium";
  if (score >= 40) return "high";
  return "very_high";
}

function fmt_usd(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getProject(id)
      .then(setProject)
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="p-8 flex items-center gap-2 text-gray-400 text-sm">
        <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        Loading project...
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="p-8">
        <div className="flex items-center gap-2 p-4 bg-red-950/40 border border-red-800 rounded-xl text-red-400 text-sm">
          <AlertCircle size={16} />
          {error ?? "Project not found"}
        </div>
        <button onClick={() => router.push("/projects")} className="mt-4 btn-secondary text-sm">
          Back to Projects
        </button>
      </div>
    );
  }

  const m = project.metrics;
  const riskTier = deriveRiskTier(m.submission_readiness_score);
  const hasResult = !!project.latest_job_id;

  return (
    <div className="p-8 max-w-4xl mx-auto">
      {/* Back + header */}
      <button
        onClick={() => router.push("/projects")}
        className="flex items-center gap-1.5 text-gray-500 hover:text-gray-300 text-sm mb-6 transition-colors"
      >
        <ArrowLeft size={14} /> All Projects
      </button>

      <div className="flex items-start justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">{project.name}</h1>
          <p className="text-gray-400 text-sm mt-1">
            {project.facility_type?.replace(/_/g, " ")}
            {project.city ? ` · ${project.city}` : ""}
            {project.state ? `, ${project.state}` : ""}
            {" · "}
            <span className="capitalize">{project.status.replace(/_/g, " ")}</span>
          </p>
        </div>

        {hasResult && (
          <button
            onClick={() => router.push(`/projects/${id}/result?job=${project.latest_job_id}`)}
            className="btn-primary flex items-center gap-2 text-sm shrink-0"
          >
            <BarChart2 size={14} />
            View Full Report
            <ExternalLink size={12} />
          </button>
        )}
      </div>

      {/* Key metrics */}
      {m.total_rooms != null ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
          <div className="card text-center">
            <div className={`text-3xl font-bold ${RISK_COLOR[riskTier]}`}>
              {m.submission_readiness_score != null ? `${Math.round(m.submission_readiness_score)}` : "—"}
              {m.submission_readiness_score != null && <span className="text-base font-normal text-gray-400">/100</span>}
            </div>
            <div className="text-xs text-gray-500 mt-1">Readiness score</div>
          </div>

          <div className="card text-center">
            <div className="text-3xl font-bold text-red-400">{m.critical_violations ?? "—"}</div>
            <div className="text-xs text-gray-500 mt-1">Critical violations</div>
          </div>

          <div className="card text-center">
            <div className="text-3xl font-bold text-orange-400">
              {m.estimated_correction_cost_usd != null ? fmt_usd(m.estimated_correction_cost_usd) : "—"}
            </div>
            <div className="text-xs text-gray-500 mt-1">Est. correction cost</div>
          </div>

          <div className="card text-center">
            <div className="text-3xl font-bold text-blue-400">
              {m.fgi_approval_probability != null ? `${Math.round(m.fgi_approval_probability)}%` : "—"}
            </div>
            <div className="text-xs text-gray-500 mt-1">FGI approval prob.</div>
          </div>
        </div>
      ) : (
        <div className="card mb-6 text-center py-8">
          <p className="text-gray-500 text-sm">No analysis data yet.</p>
          <button
            onClick={() => router.push("/upload")}
            className="mt-3 btn-primary text-sm"
          >
            Run Analysis
          </button>
        </div>
      )}

      {/* Details grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        {/* Compliance summary */}
        {project.compliance_summary && (
          <div className="card">
            <h2 className="text-white font-semibold text-sm mb-3 flex items-center gap-2">
              <AlertTriangle size={14} className="text-orange-400" /> Compliance Summary
            </h2>
            <div className="space-y-2">
              {[
                { label: "Critical", key: "critical", cls: "text-red-400" },
                { label: "High", key: "high", cls: "text-orange-400" },
                { label: "Medium", key: "medium", cls: "text-yellow-400" },
                { label: "Low", key: "low", cls: "text-blue-400" },
              ].map(({ label, key, cls }) => (
                <div key={key} className="flex items-center justify-between text-sm">
                  <span className="text-gray-400">{label}</span>
                  <span className={`font-medium ${cls}`}>
                    {(project.compliance_summary as Record<string, number>)[key] ?? 0}
                  </span>
                </div>
              ))}
              {(project.compliance_summary as Record<string, number>).total_cost_usd != null && (
                <div className="flex items-center gap-1.5 pt-2 border-t border-gray-800 text-sm">
                  <DollarSign size={12} className="text-orange-400" />
                  <span className="text-gray-400">Est. correction cost:</span>
                  <span className="text-orange-400 font-medium">
                    {fmt_usd((project.compliance_summary as Record<string, number>).total_cost_usd)}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Prediction summary */}
        {project.prediction_summary && (
          <div className="card">
            <h2 className="text-white font-semibold text-sm mb-3 flex items-center gap-2">
              <BarChart2 size={14} className="text-blue-400" /> Approval Prediction
            </h2>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-400">Risk level</span>
                <span className={`font-medium capitalize ${RISK_COLOR[(project.prediction_summary as Record<string, string>).risk_level] ?? "text-gray-400"}`}>
                  {((project.prediction_summary as Record<string, string>).risk_level ?? "—").replace("_", " ")}
                </span>
              </div>
              {(project.prediction_summary as Record<string, number>).estimated_rework_cost_usd != null && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-400">Est. rework cost</span>
                  <span className="text-white">{fmt_usd((project.prediction_summary as Record<string, number>).estimated_rework_cost_usd)}</span>
                </div>
              )}
              {(project.prediction_summary as Record<string, number>).estimated_rework_days != null && (
                <div className="flex items-center gap-1.5 text-sm">
                  <Clock size={12} className="text-blue-400" />
                  <span className="text-gray-400">Est. rework time:</span>
                  <span className="text-white">{(project.prediction_summary as Record<string, number>).estimated_rework_days}d</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Blocking issues */}
      {(project.prediction_summary as Record<string, string[]>)?.blocking_issues?.length > 0 && (
        <div className="card mb-6 border-red-900">
          <h2 className="text-red-400 font-semibold text-sm mb-3 flex items-center gap-2">
            <AlertCircle size={14} /> Blocking Issues
          </h2>
          <ul className="space-y-2">
            {((project.prediction_summary as Record<string, string[]>).blocking_issues).map((issue, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <div className="w-1.5 h-1.5 bg-red-500 rounded-full mt-2 shrink-0" />
                <span className="text-gray-300">{issue}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Approval outcome */}
      {project.outcome && (
        <div className="card mb-6">
          <h2 className="text-white font-semibold text-sm mb-3">Regulatory Outcome</h2>
          <div className="flex items-center gap-3">
            {project.outcome.approval_result === "approved" ? (
              <CheckCircle size={20} className="text-green-400" />
            ) : project.outcome.approval_result === "rejected" ? (
              <AlertTriangle size={20} className="text-red-400" />
            ) : (
              <Clock size={20} className="text-yellow-400" />
            )}
            <div>
              <p className={`font-semibold capitalize ${
                project.outcome.approval_result === "approved" ? "text-green-400" :
                project.outcome.approval_result === "rejected" ? "text-red-400" : "text-yellow-400"
              }`}>
                {project.outcome.approval_result}
                {project.outcome.regulator ? ` · ${project.outcome.regulator}` : ""}
              </p>
              {project.outcome.review_duration_days && (
                <p className="text-gray-500 text-xs">{project.outcome.review_duration_days} day review</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* View full report CTA */}
      {hasResult && (
        <div className="text-center">
          <button
            onClick={() => router.push(`/projects/${id}/result?job=${project.latest_job_id}`)}
            className="btn-primary inline-flex items-center gap-2"
          >
            <BarChart2 size={16} />
            View Full Compliance Report
          </button>
        </div>
      )}
    </div>
  );
}
