"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getSharedReport, getJobResult } from "@/lib/api";
import type { AnalysisResult, Project } from "@/lib/api";
import {
  CheckCircle,
  AlertTriangle,
  AlertCircle,
  Info,
  DollarSign,
  Clock,
  ChevronDown,
  ChevronUp,
  Printer,
} from "lucide-react";

const SEVERITY_COLOR: Record<string, string> = {
  critical: "text-red-400 bg-red-950/30 border-red-900",
  high: "text-orange-400 bg-orange-950/30 border-orange-900",
  medium: "text-yellow-400 bg-yellow-950/30 border-yellow-900",
  low: "text-blue-400 bg-blue-950/30 border-blue-900",
  advisory: "text-gray-400 bg-gray-900/30 border-gray-800",
};

const SEVERITY_DOT: Record<string, string> = {
  critical: "bg-red-500",
  high: "bg-orange-500",
  medium: "bg-yellow-400",
  low: "bg-blue-400",
  advisory: "bg-gray-500",
};

const RISK_COLOR: Record<string, string> = {
  low: "text-green-400",
  medium: "text-yellow-400",
  high: "text-orange-400",
  very_high: "text-red-400",
};

function ApprovalGauge({ probability, label }: { probability: number; label: string }) {
  const pct = Math.round(probability * 100);
  const color = pct >= 75 ? "#2ECC71" : pct >= 50 ? "#F39C12" : "#E74C3C";
  const circumference = 2 * Math.PI * 36;
  const strokeDashoffset = circumference - (pct / 100) * circumference;
  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="90" height="90" className="-rotate-90">
        <circle cx="45" cy="45" r="36" fill="none" stroke="#1f2937" strokeWidth="8" />
        <circle cx="45" cy="45" r="36" fill="none" stroke={color} strokeWidth="8"
          strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={strokeDashoffset}
          style={{ transition: "stroke-dashoffset 0.6s ease" }} />
      </svg>
      <div className="text-center -mt-1" style={{ marginTop: "-70px" }}>
        <div className="text-xl font-bold text-white" style={{ lineHeight: 1 }}>{pct}%</div>
      </div>
      <p className="text-xs text-gray-400 text-center mt-14">{label}</p>
    </div>
  );
}

function CollapsibleRoom({
  result,
}: {
  result: AnalysisResult["compliance_report"]["room_results"][0];
}) {
  const [open, setOpen] = useState(result.violations.length > 0);
  return (
    <div className="border border-gray-800 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-900 hover:bg-gray-800 transition-colors"
      >
        <div className="flex items-center gap-3">
          {result.violations.length === 0 ? (
            <CheckCircle size={14} className="text-green-400 shrink-0" />
          ) : (
            <AlertTriangle size={14} className="text-orange-400 shrink-0" />
          )}
          <span className="text-white text-sm font-medium">{result.room_label}</span>
          <span className="text-gray-500 text-xs">{result.room_type.replace(/_/g, " ")}</span>
        </div>
        <div className="flex items-center gap-3">
          {result.violations.length > 0 && (
            <span className="text-xs text-orange-400">{result.violations.length} violation{result.violations.length !== 1 ? "s" : ""}</span>
          )}
          {open ? <ChevronUp size={14} className="text-gray-500" /> : <ChevronDown size={14} className="text-gray-500" />}
        </div>
      </button>
      {open && (
        <div className="px-4 py-3 space-y-3 bg-gray-950">
          {result.llm_interpretation && (
            <div className="flex gap-2 p-3 bg-blue-950/20 border border-blue-900 rounded-lg">
              <Info size={14} className="text-blue-400 shrink-0 mt-0.5" />
              <p className="text-blue-300 text-xs">{result.llm_interpretation}</p>
            </div>
          )}
          {result.violations.map((v) => (
            <div key={v.violation_id} className={`border rounded-lg p-3 ${SEVERITY_COLOR[v.severity]}`}>
              <div className="flex items-start justify-between gap-2 mb-1">
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full shrink-0 mt-1 ${SEVERITY_DOT[v.severity]}`} />
                  <span className="text-sm font-medium capitalize">{v.severity}</span>
                  <span className="text-xs opacity-70">{v.constraint_type.replace(/_/g, " ")}</span>
                </div>
                {v.estimated_correction_cost_usd != null && (
                  <span className="text-xs opacity-80 flex items-center gap-1 whitespace-nowrap">
                    <DollarSign size={10} />{v.estimated_correction_cost_usd.toLocaleString()}
                  </span>
                )}
              </div>
              <p className="text-xs mt-1 opacity-90">{v.description}</p>
              {v.actual_value != null && v.required_value != null && (
                <p className="text-xs mt-1 opacity-70">
                  Actual: {v.actual_value} {v.unit} · Required: {v.required_value} {v.unit}
                </p>
              )}
              {v.remediation_suggestion && (
                <p className="text-xs mt-2 italic opacity-75">{v.remediation_suggestion}</p>
              )}
            </div>
          ))}
          {result.violations.length === 0 && (
            <p className="text-green-600 text-xs">All checked rules passed for this room.</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function SharedReportPage() {
  const { token } = useParams<{ token: string }>();
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "compliance" | "prediction">("overview");

  useEffect(() => {
    if (!token) { setError("Invalid share link"); setLoading(false); return; }
    getSharedReport(token)
      .then(async ({ project: proj, job_id }) => {
        setProject(proj);
        if (job_id) {
          const r = await getJobResult(job_id);
          setResult(r);
        } else {
          setError("No analysis data available for this project yet.");
        }
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="flex items-center gap-3 text-gray-400 text-sm">
          <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          Loading compliance report...
        </div>
      </div>
    );
  }

  if (error || !result || !project) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center p-8">
        <div className="max-w-md w-full space-y-4 text-center">
          <div className="text-4xl">🏥</div>
          <h1 className="text-white text-xl font-bold">MedBlueprints</h1>
          <div className="flex items-center gap-2 p-4 bg-red-950/40 border border-red-800 rounded-xl text-red-400 text-sm">
            <AlertCircle size={16} />
            {error ?? "Report not found"}
          </div>
        </div>
      </div>
    );
  }

  const r = result.compliance_report;
  const pred = result.prediction;
  const readinessPct = Math.round(pred.submission_readiness_score * 100);

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <div className="border-b border-gray-800 bg-gray-900">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 bg-blue-600 rounded-lg flex items-center justify-center text-white text-xs font-bold">M</div>
            <span className="text-white font-semibold text-sm">MedBlueprints</span>
            <span className="text-gray-600 text-xs">Compliance Report</span>
          </div>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors"
          >
            <Printer size={13} /> Print / Save PDF
          </button>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Project title */}
        <div>
          <h1 className="text-2xl font-bold text-white">{project.name}</h1>
          <p className="text-gray-400 text-sm mt-1">
            {project.facility_type?.replace(/_/g, " ")} ·{" "}
            {result.parse_result.rooms.length} rooms ·{" "}
            {result.parse_result.total_area_sqft?.toLocaleString() ?? "—"} sqft
            {result.demo_mode && <span className="text-yellow-400"> · Demo</span>}
          </p>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
            <div className={`text-3xl font-bold ${r.overall_compliant ? "text-green-400" : "text-red-400"}`}>
              {r.overall_compliant ? "✓" : "✗"}
            </div>
            <div className="text-xs text-gray-500 mt-1">Compliant</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
            <div className="text-3xl font-bold text-red-400">{r.critical_violations}</div>
            <div className="text-xs text-gray-500 mt-1">Critical violations</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
            <div className={`text-3xl font-bold ${RISK_COLOR[pred.overall_risk_level]}`}>{readinessPct}%</div>
            <div className="text-xs text-gray-500 mt-1">Submission readiness</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
            <div className="text-3xl font-bold text-orange-400">
              ${(r.estimated_total_correction_cost_usd / 1000).toFixed(0)}K
            </div>
            <div className="text-xs text-gray-500 mt-1">Est. correction cost</div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-gray-800">
          {(["overview", "compliance", "prediction"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px capitalize ${
                activeTab === tab
                  ? "border-blue-500 text-blue-400"
                  : "border-transparent text-gray-500 hover:text-gray-300"
              }`}
            >
              {tab === "prediction" ? "Approval" : tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        {/* Tab: Overview */}
        {activeTab === "overview" && (
          <div className="space-y-4">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <h2 className="text-white font-semibold mb-4">Detected Rooms</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {result.parse_result.rooms.map((room) => {
                  const violations = r.room_results.find((rr) => rr.room_id === room.id)?.violations ?? [];
                  const criticals = violations.filter((v) => v.severity === "critical").length;
                  return (
                    <div key={room.id} className="flex items-center justify-between p-3 bg-gray-950 rounded-lg border border-gray-800">
                      <div>
                        <p className="text-white text-sm font-medium">{room.label}</p>
                        <p className="text-gray-500 text-xs">
                          {room.room_type.replace(/_/g, " ")} ·{" "}
                          {room.area_sqft != null ? `${room.area_sqft.toFixed(0)} sqft` : "area unknown"}
                        </p>
                      </div>
                      {criticals > 0 && (
                        <span className="text-xs text-red-400 flex items-center gap-1">
                          <AlertCircle size={10} /> {criticals}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {r.summary && (
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                <h2 className="text-white font-semibold mb-2">Summary</h2>
                <p className="text-gray-400 text-sm">{r.summary}</p>
              </div>
            )}
          </div>
        )}

        {/* Tab: Compliance */}
        {activeTab === "compliance" && (
          <div className="space-y-4">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <div className="grid grid-cols-5 gap-3 text-center">
                {[
                  { label: "Critical", count: r.critical_violations, cls: "text-red-400" },
                  { label: "High", count: r.high_violations, cls: "text-orange-400" },
                  { label: "Medium", count: r.medium_violations, cls: "text-yellow-400" },
                  { label: "Low", count: r.low_violations, cls: "text-blue-400" },
                  { label: "Total", count: r.total_violations, cls: "text-white" },
                ].map(({ label, count, cls }) => (
                  <div key={label}>
                    <div className={`text-2xl font-bold ${cls}`}>{count}</div>
                    <div className="text-xs text-gray-500 mt-1">{label}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              {r.room_results.map((rr) => (
                <CollapsibleRoom key={rr.room_id} result={rr} />
              ))}
            </div>
          </div>
        )}

        {/* Tab: Prediction */}
        {activeTab === "prediction" && (
          <div className="space-y-6">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <h2 className="text-white font-semibold mb-6">Approval Probability by Regulator</h2>
              <div className="flex flex-wrap justify-center gap-12">
                {pred.regulator_predictions.map((rp) => (
                  <ApprovalGauge key={rp.regulator} probability={rp.approval_probability} label={rp.regulator} />
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                <h3 className="text-white font-semibold mb-3">Submission Readiness</h3>
                <div className="w-full bg-gray-800 rounded-full h-2 mb-2">
                  <div
                    className={`h-2 rounded-full ${readinessPct >= 75 ? "bg-green-500" : readinessPct >= 50 ? "bg-yellow-500" : "bg-red-500"}`}
                    style={{ width: `${readinessPct}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs mt-1 mb-4">
                  <span className="text-gray-500">Risk: <span className={RISK_COLOR[pred.overall_risk_level]}>{pred.overall_risk_level.replace("_", " ")}</span></span>
                  <span className="text-gray-400">{readinessPct}%</span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-2 text-gray-400">
                    <DollarSign size={13} className="text-orange-400" />
                    Est. rework cost: <strong className="text-white">${pred.estimated_rework_cost_usd.toLocaleString()}</strong>
                  </div>
                  <div className="flex items-center gap-2 text-gray-400">
                    <Clock size={13} className="text-blue-400" />
                    Est. rework time: <strong className="text-white">{pred.estimated_rework_days} days</strong>
                  </div>
                </div>
              </div>

              <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                <h3 className="text-white font-semibold mb-3">Review Timeline</h3>
                <div className="space-y-2">
                  {pred.regulator_predictions.map((rp) => (
                    <div key={rp.regulator} className="flex items-center justify-between text-sm">
                      <span className="text-gray-400">{rp.regulator}</span>
                      <span className="text-white">{rp.expected_review_days}d</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {pred.top_blocking_issues.length > 0 && (
              <div className="bg-gray-900 border border-red-900 rounded-xl p-5">
                <h3 className="text-red-400 font-semibold mb-3 flex items-center gap-2">
                  <AlertCircle size={14} /> Blocking Issues
                </h3>
                <ul className="space-y-2">
                  {pred.top_blocking_issues.map((issue, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <div className="w-1.5 h-1.5 bg-red-500 rounded-full mt-2 shrink-0" />
                      <span className="text-gray-300">{issue}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {pred.recommended_actions.length > 0 && (
              <div className="bg-gray-900 border border-green-900 rounded-xl p-5">
                <h3 className="text-green-400 font-semibold mb-3 flex items-center gap-2">
                  <CheckCircle size={14} /> Recommended Actions
                </h3>
                <ul className="space-y-2">
                  {pred.recommended_actions.map((action, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <div className="w-1.5 h-1.5 bg-green-500 rounded-full mt-2 shrink-0" />
                      <span className="text-gray-300">{action}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="pt-6 border-t border-gray-800 text-center text-xs text-gray-600">
          Generated by MedBlueprints · AI Regulatory Compliance Platform ·{" "}
          {new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}
        </div>
      </div>
    </div>
  );
}
