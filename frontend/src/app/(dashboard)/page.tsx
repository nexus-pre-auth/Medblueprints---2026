"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getDashboardStats, listProjects, getOutcomeStats, getRuleStats } from "@/lib/api";
import type { Project } from "@/lib/api";
import {
  AlertTriangle, CheckCircle, Clock, TrendingUp, Upload,
  Database, BookOpen, ArrowRight,
} from "lucide-react";

interface Stats {
  total_projects: number;
  analyzed_projects: number;
  approved_projects: number;
  avg_submission_readiness: number;
  avg_critical_violations: number;
}

function ReadinessGauge({ score }: { score: number }) {
  const color = score >= 85 ? "#22c55e" : score >= 65 ? "#eab308" : "#ef4444";
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative w-24 h-24">
        <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
          <circle cx="50" cy="50" r="40" fill="none" stroke="#1f2937" strokeWidth="12" />
          <circle
            cx="50" cy="50" r="40" fill="none"
            stroke={color} strokeWidth="12"
            strokeDasharray={`${score * 2.51} 251`}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center rotate-90">
          <span className="text-xl font-bold text-white">{score.toFixed(0)}</span>
        </div>
      </div>
      <span className="text-xs text-gray-400">Avg Readiness</span>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    draft: "badge-low",
    analyzing: "badge-medium",
    reviewed: "badge-high",
    submitted: "badge-medium",
    approved: "badge-compliant",
    rejected: "badge-critical",
    conditional: "badge-high",
  };
  return <span className={map[status] ?? "badge-low"}>{status}</span>;
}

function ViolationBadge({ count, level }: { count: number | null; level: string }) {
  if (count === null) return <span className="text-gray-600">—</span>;
  if (count === 0) return <span className="text-green-500 text-sm font-semibold">0</span>;
  const cls = level === "critical" ? "text-red-400" : level === "high" ? "text-orange-400" : "text-yellow-400";
  return <span className={`text-sm font-bold ${cls}`}>{count}</span>;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [outcomeStats, setOutcomeStats] = useState<Record<string, unknown> | null>(null);
  const [ruleStats, setRuleStats] = useState<{ total_rules: number; sources: string[] } | null>(null);

  useEffect(() => {
    Promise.all([
      getDashboardStats().catch(() => null),
      listProjects({ }).catch(() => ({ projects: [] })),
      getOutcomeStats().catch(() => null),
      getRuleStats().catch(() => null),
    ]).then(([s, p, o, r]) => {
      setStats(s as Stats);
      setProjects((p as { projects: Project[] }).projects.slice(0, 8));
      setOutcomeStats(o as Record<string, unknown>);
      setRuleStats(r as { total_rules: number; sources: string[] });
    });
  }, []);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-gray-400 text-sm mt-1">AI Regulatory Intelligence for Healthcare Construction</p>
        </div>
        <Link href="/upload" className="btn-primary flex items-center gap-2">
          <Upload size={16} />
          Upload Blueprint
        </Link>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="card">
          <div className="text-gray-400 text-xs font-medium uppercase tracking-wider mb-2">Total Projects</div>
          <div className="text-3xl font-bold text-white">{stats?.total_projects ?? "—"}</div>
        </div>
        <div className="card">
          <div className="text-gray-400 text-xs font-medium uppercase tracking-wider mb-2">Analyzed</div>
          <div className="text-3xl font-bold text-white">{stats?.analyzed_projects ?? "—"}</div>
        </div>
        <div className="card">
          <div className="text-gray-400 text-xs font-medium uppercase tracking-wider mb-2">Approved</div>
          <div className="text-3xl font-bold text-green-400">{stats?.approved_projects ?? "—"}</div>
        </div>
        <div className="card flex items-center gap-4">
          {stats ? (
            <ReadinessGauge score={stats.avg_submission_readiness} />
          ) : (
            <div className="text-gray-600 text-sm">Loading...</div>
          )}
        </div>
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Project table */}
        <div className="lg:col-span-2 card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-white font-semibold">Recent Projects</h2>
            <Link href="/projects" className="text-blue-400 text-sm hover:text-blue-300 flex items-center gap-1">
              View all <ArrowRight size={14} />
            </Link>
          </div>

          {projects.length === 0 ? (
            <div className="text-center py-12">
              <Upload size={32} className="text-gray-700 mx-auto mb-3" />
              <p className="text-gray-500 text-sm">No projects yet.</p>
              <Link href="/upload" className="btn-primary inline-flex items-center gap-2 mt-4 text-sm">
                Upload your first blueprint
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800">
                    <th className="text-left pb-3 font-medium">Project</th>
                    <th className="text-left pb-3 font-medium">Status</th>
                    <th className="text-right pb-3 font-medium">Critical</th>
                    <th className="text-right pb-3 font-medium">Readiness</th>
                    <th className="text-right pb-3 font-medium">FGI %</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {projects.map((p) => (
                    <tr key={p.project_id} className="hover:bg-gray-800/50 transition-colors">
                      <td className="py-3">
                        <Link href={`/projects/${p.project_id}`} className="text-white hover:text-blue-400 font-medium">
                          {p.name}
                        </Link>
                        <div className="text-gray-500 text-xs mt-0.5">{p.facility_type}</div>
                      </td>
                      <td className="py-3"><StatusBadge status={p.status} /></td>
                      <td className="py-3 text-right">
                        <ViolationBadge count={p.metrics.critical_violations} level="critical" />
                      </td>
                      <td className="py-3 text-right text-gray-300">
                        {p.metrics.submission_readiness_score != null
                          ? `${p.metrics.submission_readiness_score.toFixed(0)}/100`
                          : "—"}
                      </td>
                      <td className="py-3 text-right text-gray-300">
                        {p.metrics.fgi_approval_probability != null
                          ? `${p.metrics.fgi_approval_probability.toFixed(0)}%`
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right column */}
        <div className="space-y-4">
          {/* Rule library */}
          <div className="card">
            <div className="flex items-center gap-2 mb-3">
              <BookOpen size={16} className="text-blue-400" />
              <h3 className="text-white font-semibold text-sm">Regulatory Knowledge Graph</h3>
            </div>
            <div className="text-3xl font-bold text-white mb-1">{ruleStats?.total_rules ?? "—"}</div>
            <div className="text-gray-400 text-xs">rules loaded</div>
            <div className="mt-3 flex flex-wrap gap-1">
              {(ruleStats?.sources ?? []).map((s) => (
                <span key={s} className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">{s}</span>
              ))}
            </div>
            <Link href="/compliance" className="mt-4 text-blue-400 text-xs flex items-center gap-1 hover:text-blue-300">
              Browse rules <ArrowRight size={12} />
            </Link>
          </div>

          {/* Dataset moat */}
          <div className="card">
            <div className="flex items-center gap-2 mb-3">
              <Database size={16} className="text-purple-400" />
              <h3 className="text-white font-semibold text-sm">Strategic Moat</h3>
            </div>
            <div className="text-3xl font-bold text-white mb-1">
              {(outcomeStats as Record<string, number>)?.total_projects ?? 0}
            </div>
            <div className="text-gray-400 text-xs">projects in outcome dataset</div>
            <div className="mt-3 text-xs text-gray-500">
              {(outcomeStats as Record<string, number>)?.labeled_projects ?? 0} labeled ·{" "}
              {(outcomeStats as Record<string, number>)?.model_training_ready
                ? "✓ Model training ready"
                : `Need ${50 - ((outcomeStats as Record<string, number>)?.labeled_projects ?? 0)} more for model training`}
            </div>
            <Link href="/dataset" className="mt-4 text-purple-400 text-xs flex items-center gap-1 hover:text-purple-300">
              View dataset intelligence <ArrowRight size={12} />
            </Link>
          </div>

          {/* Quick actions */}
          <div className="card">
            <h3 className="text-white font-semibold text-sm mb-3">Quick Actions</h3>
            <div className="space-y-2">
              <Link href="/upload" className="flex items-center gap-2 text-sm text-gray-300 hover:text-white p-2 rounded-lg hover:bg-gray-800 transition-colors">
                <Upload size={14} className="text-blue-400" />
                Upload & analyze blueprint
              </Link>
              <Link href="/simulate" className="flex items-center gap-2 text-sm text-gray-300 hover:text-white p-2 rounded-lg hover:bg-gray-800 transition-colors">
                <TrendingUp size={14} className="text-green-400" />
                Run approval simulator
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
