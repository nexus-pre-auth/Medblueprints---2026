"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { getJobResult, getProject, recordOutcome } from "@/lib/api";
import type { AnalysisResult, Project } from "@/lib/api";
import {
  CheckCircle,
  AlertTriangle,
  AlertCircle,
  Info,
  Layers,
  BarChart2,
  Map,
  DollarSign,
  Clock,
  ChevronDown,
  ChevronUp,
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
        <circle
          cx="45"
          cy="45"
          r="36"
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          style={{ transition: "stroke-dashoffset 0.6s ease" }}
        />
      </svg>
      <div className="text-center -mt-1" style={{ marginTop: "-70px" }}>
        <div className="text-xl font-bold text-white" style={{ lineHeight: 1 }}>
          {pct}%
        </div>
      </div>
      <p className="text-xs text-gray-400 text-center mt-14">{label}</p>
    </div>
  );
}

function SVGOverlay({ svgContent }: { svgContent: string }) {
  if (!svgContent) return null;
  return (
    <div
      className="w-full overflow-auto rounded-lg bg-gray-900 border border-gray-800 p-2"
      dangerouslySetInnerHTML={{ __html: svgContent }}
    />
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
          {result.passed_rules.length > 0 && (
            <span className="text-xs text-green-600">{result.passed_rules.length} passed</span>
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
                    <DollarSign size={10} />
                    {v.estimated_correction_cost_usd.toLocaleString()}
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

export default function ResultPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const jobId = searchParams.get("job");
  const router = useRouter();

  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "compliance" | "prediction" | "ar">("overview");
  const [recordingOutcome, setRecordingOutcome] = useState(false);
  const [outcomeRecorded, setOutcomeRecorded] = useState(false);

  useEffect(() => {
    if (!jobId) { setError("No job ID in URL"); setLoading(false); return; }
    Promise.all([
      getJobResult(jobId),
      getProject(id).catch(() => null),
    ])
      .then(([r, p]) => {
        setResult(r);
        setProject(p as Project | null);
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [jobId, id]);

  const handleRecordApproved = async () => {
    if (!id || outcomeRecorded) return;
    setRecordingOutcome(true);
    try {
      await recordOutcome(id, { approval_result: "approved" });
      setOutcomeRecorded(true);
    } finally {
      setRecordingOutcome(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 text-gray-400 text-sm flex items-center gap-2">
        <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        Loading analysis results...
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="p-8">
        <div className="flex items-center gap-2 p-4 bg-red-950/40 border border-red-800 rounded-xl text-red-400 text-sm">
          <AlertCircle size={16} />
          {error ?? "Result not found"}
        </div>
        <button onClick={() => router.push("/upload")} className="mt-4 btn-secondary text-sm">
          Back to Upload
        </button>
      </div>
    );
  }

  const r = result.compliance_report;
  const pred = result.prediction;
  const svgOverlay = (result.ar_scene as Record<string, string>)?.svg ?? "";

  const readinessPct = Math.round(pred.submission_readiness_score * 100);
  const fgiPred = pred.regulator_predictions.find((p) => p.regulator.toLowerCase().includes("fgi"));
  const ahjPred = pred.regulator_predictions.find((p) => p.regulator.toLowerCase().includes("ahj") || p.regulator.toLowerCase().includes("local"));
  const statePred = pred.regulator_predictions.find((p) => p.regulator.toLowerCase().includes("state"));

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">
            {project?.name ?? "Analysis Result"}
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            {project?.facility_type?.replace(/_/g, " ") ?? "Healthcare Facility"} ·{" "}
            {result.parse_result.rooms.length} rooms detected ·{" "}
            {result.demo_mode && <span className="text-yellow-400">Demo mode · </span>}
            Job {jobId?.slice(0, 8)}
          </p>
        </div>
        <div className="flex gap-2">
          {!outcomeRecorded ? (
            <button
              onClick={handleRecordApproved}
              disabled={recordingOutcome}
              className="btn-secondary text-xs flex items-center gap-1"
            >
              <CheckCircle size={12} />
              {recordingOutcome ? "Saving..." : "Record Approved"}
            </button>
          ) : (
            <span className="text-green-400 text-xs flex items-center gap-1">
              <CheckCircle size={12} /> Outcome saved
            </span>
          )}
          <button onClick={() => router.push("/upload")} className="btn-secondary text-xs">
            New Analysis
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div className="card text-center">
          <div className={`text-3xl font-bold ${r.overall_compliant ? "text-green-400" : "text-red-400"}`}>
            {r.overall_compliant ? "✓" : "✗"}
          </div>
          <div className="text-xs text-gray-500 mt-1">Compliant</div>
        </div>
        <div className="card text-center">
          <div className="text-3xl font-bold text-red-400">{r.critical_violations}</div>
          <div className="text-xs text-gray-500 mt-1">Critical violations</div>
        </div>
        <div className="card text-center">
          <div className={`text-3xl font-bold ${RISK_COLOR[pred.overall_risk_level]}`}>
            {readinessPct}%
          </div>
          <div className="text-xs text-gray-500 mt-1">Submission readiness</div>
        </div>
        <div className="card text-center">
          <div className="text-3xl font-bold text-orange-400">
            ${(r.estimated_total_correction_cost_usd / 1000).toFixed(0)}K
          </div>
          <div className="text-xs text-gray-500 mt-1">Est. correction cost</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-800">
        {[
          { key: "overview", label: "Overview", icon: BarChart2 },
          { key: "compliance", label: "Compliance", icon: AlertTriangle },
          { key: "prediction", label: "Approval", icon: CheckCircle },
          { key: "ar", label: "AR Overlay", icon: Map },
        ].map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key as typeof activeTab)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
              activeTab === key
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-gray-500 hover:text-gray-300"
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {/* Tab: Overview */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          {/* Parse result */}
          <div className="card">
            <div className="flex items-center gap-2 mb-4">
              <Layers size={16} className="text-blue-400" />
              <h2 className="text-white font-semibold">Detected Rooms</h2>
              <span className="text-gray-500 text-xs ml-auto">
                Total area: {result.parse_result.total_area_sqft?.toLocaleString() ?? "—"} sqft ·{" "}
                Confidence: {(result.parse_result.parse_confidence * 100).toFixed(0)}%
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {result.parse_result.rooms.map((room) => {
                const violations = r.room_results.find((rr) => rr.room_id === room.id)?.violations ?? [];
                const criticals = violations.filter((v) => v.severity === "critical").length;
                return (
                  <div key={room.id} className="flex items-center justify-between p-3 bg-gray-900 rounded-lg border border-gray-800">
                    <div>
                      <p className="text-white text-sm font-medium">{room.label}</p>
                      <p className="text-gray-500 text-xs">
                        {room.room_type.replace(/_/g, " ")} ·{" "}
                        {room.area_sqft != null ? `${room.area_sqft.toFixed(0)} sqft` : "area unknown"}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {criticals > 0 && (
                        <span className="text-xs text-red-400 flex items-center gap-1">
                          <AlertCircle size={10} /> {criticals}
                        </span>
                      )}
                      <span className="text-xs text-gray-600">{(room.confidence * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Facility graph summary */}
          <div className="card">
            <h2 className="text-white font-semibold mb-3">Facility Graph</h2>
            <div className="flex gap-8 text-center">
              <div>
                <div className="text-2xl font-bold text-white">{result.facility_graph.node_count}</div>
                <div className="text-xs text-gray-500 mt-1">Nodes</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-white">{result.facility_graph.edge_count}</div>
                <div className="text-xs text-gray-500 mt-1">Relationships</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-white">{result.parse_result.corridors.length}</div>
                <div className="text-xs text-gray-500 mt-1">Corridors</div>
              </div>
            </div>
          </div>

          {/* Ingestion warnings */}
          {result.ingestion_warnings.length > 0 && (
            <div className="card border-yellow-900">
              <h2 className="text-yellow-400 font-semibold mb-2 flex items-center gap-2">
                <AlertTriangle size={14} /> Ingestion Warnings
              </h2>
              <ul className="space-y-1">
                {result.ingestion_warnings.map((w, i) => (
                  <li key={i} className="text-yellow-600 text-xs">{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Tab: Compliance */}
      {activeTab === "compliance" && (
        <div className="space-y-4">
          {/* Summary bar */}
          <div className="card">
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
            {r.summary && (
              <p className="mt-4 text-gray-400 text-sm border-t border-gray-800 pt-4">{r.summary}</p>
            )}
          </div>

          {/* Room-by-room */}
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
          {/* Gauges */}
          <div className="card">
            <h2 className="text-white font-semibold mb-6">Approval Probability by Regulator</h2>
            <div className="flex flex-wrap justify-center gap-12">
              {pred.regulator_predictions.map((rp) => (
                <ApprovalGauge
                  key={rp.regulator}
                  probability={rp.approval_probability}
                  label={rp.regulator}
                />
              ))}
            </div>
          </div>

          {/* Readiness + risk */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="card">
              <h3 className="text-white font-semibold mb-3">Submission Readiness</h3>
              <div className="progress-bar mb-2">
                <div
                  className={`progress-fill ${readinessPct >= 75 ? "bg-green-500" : readinessPct >= 50 ? "bg-yellow-500" : "bg-red-500"}`}
                  style={{ width: `${readinessPct}%` }}
                />
              </div>
              <div className="flex justify-between text-xs mt-1">
                <span className="text-gray-500">Risk: <span className={RISK_COLOR[pred.overall_risk_level]}>{pred.overall_risk_level.replace("_", " ")}</span></span>
                <span className="text-gray-400">{readinessPct}%</span>
              </div>
              <div className="mt-4 space-y-2 text-sm">
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

            <div className="card">
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

          {/* Blocking issues */}
          {pred.top_blocking_issues.length > 0 && (
            <div className="card border-red-900">
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

          {/* Recommended actions */}
          {pred.recommended_actions.length > 0 && (
            <div className="card border-green-900">
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

      {/* Tab: AR Overlay */}
      {activeTab === "ar" && (
        <div className="space-y-4">
          <div className="card">
            <div className="flex items-center gap-2 mb-4">
              <Map size={16} className="text-blue-400" />
              <h2 className="text-white font-semibold">Compliance Heatmap</h2>
              <span className="ml-auto text-xs text-gray-500">
                Red = critical · Orange = high · Yellow = medium · Blue = low · Green = compliant
              </span>
            </div>
            {svgOverlay ? (
              <SVGOverlay svgContent={svgOverlay} />
            ) : (
              <p className="text-gray-500 text-sm">SVG overlay not available for this analysis.</p>
            )}
          </div>

          {/* WebXR metadata */}
          {result.ar_scene && (
            <div className="card">
              <h3 className="text-white font-semibold mb-3">AR Scene Metadata</h3>
              <pre className="text-xs text-gray-400 overflow-auto max-h-60">
                {JSON.stringify(
                  { ...(result.ar_scene as Record<string, unknown>), svg: svgOverlay ? "[SVG content]" : undefined },
                  null,
                  2
                )}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
