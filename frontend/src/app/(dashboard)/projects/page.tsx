"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listProjects, getDashboardStats, recordOutcome } from "@/lib/api";
import type { Project } from "@/lib/api";
import {
  FolderOpen,
  CheckCircle,
  AlertTriangle,
  Clock,
  BarChart2,
  ChevronRight,
  Plus,
} from "lucide-react";

const STATUS_STYLE: Record<string, string> = {
  pending: "text-gray-400 bg-gray-900",
  analyzing: "text-blue-400 bg-blue-950/30",
  analyzed: "text-green-400 bg-green-950/30",
  approved: "text-green-400 bg-green-950/30",
  rejected: "text-red-400 bg-red-950/30",
  revision_required: "text-yellow-400 bg-yellow-950/30",
};

export default function ProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [stats, setStats] = useState<Record<string, number> | null>(null);
  const [loading, setLoading] = useState(true);
  const [recordingId, setRecordingId] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      listProjects(),
      getDashboardStats().catch(() => null),
    ]).then(([{ projects: ps }, s]) => {
      setProjects(ps);
      setStats(s as Record<string, number> | null);
    }).finally(() => setLoading(false));
  }, []);

  const handleRecordOutcome = async (projectId: string, result: "approved" | "rejected") => {
    setRecordingId(projectId);
    try {
      await recordOutcome(projectId, { approval_result: result });
      // Refresh list
      const { projects: ps } = await listProjects();
      setProjects(ps);
    } finally {
      setRecordingId(null);
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <FolderOpen size={24} className="text-blue-400" />
          <h1 className="text-2xl font-bold text-white">Projects</h1>
        </div>
        <button
          onClick={() => router.push("/upload")}
          className="btn-primary flex items-center gap-2 text-sm"
        >
          <Plus size={14} /> New Analysis
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          {[
            { label: "Total projects", value: stats.total_projects ?? 0, cls: "text-white" },
            { label: "Analyzed", value: stats.analyzed_projects ?? 0, cls: "text-blue-400" },
            { label: "Approved", value: stats.approved_projects ?? 0, cls: "text-green-400" },
            { label: "Avg readiness", value: `${Math.round((stats.avg_submission_readiness ?? 0) * 100)}%`, cls: "text-yellow-400" },
          ].map(({ label, value, cls }) => (
            <div key={label} className="card text-center">
              <div className={`text-2xl font-bold ${cls}`}>{value}</div>
              <div className="text-xs text-gray-500 mt-1">{label}</div>
            </div>
          ))}
        </div>
      )}

      {loading ? (
        <div className="text-gray-400 text-sm flex items-center gap-2">
          <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          Loading projects...
        </div>
      ) : projects.length === 0 ? (
        <div className="card text-center py-16">
          <FolderOpen size={40} className="text-gray-700 mx-auto mb-3" />
          <p className="text-gray-500 text-sm">No projects yet.</p>
          <button
            onClick={() => router.push("/upload")}
            className="mt-4 btn-primary text-sm"
          >
            Upload your first blueprint
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {projects.map((project) => {
            const m = project.metrics;
            const hasOutcome = project.outcome !== null;
            return (
              <div
                key={project.project_id}
                className="card hover:border-gray-700 transition-colors cursor-pointer"
                onClick={() => router.push(`/projects/${project.project_id}`)}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <h3 className="text-white font-semibold truncate">{project.name}</h3>
                      <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${STATUS_STYLE[project.status] ?? STATUS_STYLE.pending}`}>
                        {project.status.replace(/_/g, " ")}
                      </span>
                    </div>
                    <p className="text-gray-500 text-xs">
                      {project.facility_type.replace(/_/g, " ")} ·{" "}
                      {project.city ? `${project.city}, ` : ""}{project.state ?? ""} ·{" "}
                      {new Date(project.created_at).toLocaleDateString()}
                    </p>

                    {/* Metrics row */}
                    {m.total_rooms != null && (
                      <div className="flex flex-wrap gap-4 mt-3 text-xs">
                        {m.total_rooms != null && (
                          <span className="text-gray-400">{m.total_rooms} rooms</span>
                        )}
                        {m.total_area_sqft != null && (
                          <span className="text-gray-400">{m.total_area_sqft.toLocaleString()} sqft</span>
                        )}
                        {m.critical_violations != null && (
                          <span className={m.critical_violations > 0 ? "text-red-400" : "text-green-600"}>
                            {m.critical_violations} critical
                          </span>
                        )}
                        {m.submission_readiness_score != null && (
                          <span className="text-gray-400">
                            Readiness: {Math.round(m.submission_readiness_score)}%
                          </span>
                        )}
                        {m.fgi_approval_probability != null && (
                          <span className="text-blue-400">
                            FGI: {Math.round(m.fgi_approval_probability)}%
                          </span>
                        )}
                        {m.estimated_correction_cost_usd != null && (
                          <span className="text-orange-400">
                            ${(m.estimated_correction_cost_usd / 1000).toFixed(0)}K est.
                          </span>
                        )}
                      </div>
                    )}

                    {/* Outcome badge */}
                    {project.outcome && (
                      <div className="mt-2 flex items-center gap-2 text-xs">
                        {project.outcome.approval_result === "approved" ? (
                          <CheckCircle size={12} className="text-green-400" />
                        ) : project.outcome.approval_result === "rejected" ? (
                          <AlertTriangle size={12} className="text-red-400" />
                        ) : (
                          <Clock size={12} className="text-yellow-400" />
                        )}
                        <span className={project.outcome.approval_result === "approved" ? "text-green-400" : project.outcome.approval_result === "rejected" ? "text-red-400" : "text-yellow-400"}>
                          {project.outcome.approval_result.replace(/_/g, " ")}
                          {project.outcome.regulator ? ` · ${project.outcome.regulator}` : ""}
                          {project.outcome.review_duration_days ? ` · ${project.outcome.review_duration_days}d review` : ""}
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {/* Record outcome buttons (only for analyzed projects without outcome) */}
                    {project.status === "analyzed" && !hasOutcome && (
                      <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => handleRecordOutcome(project.project_id, "approved")}
                          disabled={recordingId === project.project_id}
                          className="text-xs px-2 py-1 bg-green-950/40 border border-green-900 text-green-400 rounded hover:bg-green-900/40 transition-colors"
                        >
                          Approved
                        </button>
                        <button
                          onClick={() => handleRecordOutcome(project.project_id, "rejected")}
                          disabled={recordingId === project.project_id}
                          className="text-xs px-2 py-1 bg-red-950/40 border border-red-900 text-red-400 rounded hover:bg-red-900/40 transition-colors"
                        >
                          Rejected
                        </button>
                      </div>
                    )}
                    <ChevronRight size={16} className="text-gray-600" />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
