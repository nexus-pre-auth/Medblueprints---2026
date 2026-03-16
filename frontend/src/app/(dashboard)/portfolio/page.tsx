"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getPortfolioRisk } from "@/lib/api";
import type { PortfolioRiskStats, PortfolioRiskProject } from "@/lib/api";
import {
  AlertTriangle,
  DollarSign,
  Clock,
  ChevronRight,
  Upload,
  TrendingUp,
  ShieldCheck,
} from "lucide-react";

function fmt_usd(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

const TIER_CONFIG = {
  very_high: {
    label: "Very High Risk",
    color: "border-red-700 bg-red-950/30",
    badge: "bg-red-900/60 text-red-300 border border-red-700",
    bar: "bg-red-500",
    dot: "bg-red-500",
  },
  high: {
    label: "High Risk",
    color: "border-orange-700 bg-orange-950/30",
    badge: "bg-orange-900/60 text-orange-300 border border-orange-700",
    bar: "bg-orange-500",
    dot: "bg-orange-500",
  },
  medium: {
    label: "Medium Risk",
    color: "border-yellow-700 bg-yellow-950/20",
    badge: "bg-yellow-900/60 text-yellow-300 border border-yellow-700",
    bar: "bg-yellow-500",
    dot: "bg-yellow-500",
  },
  low: {
    label: "Low Risk",
    color: "border-green-800 bg-green-950/20",
    badge: "bg-green-900/60 text-green-300 border border-green-700",
    bar: "bg-green-500",
    dot: "bg-green-500",
  },
};

function ProjectRiskCard({ project }: { project: PortfolioRiskProject }) {
  const tier = project.risk_tier in TIER_CONFIG ? project.risk_tier : "low";
  const cfg = TIER_CONFIG[tier as keyof typeof TIER_CONFIG];
  return (
    <Link
      href={`/projects/${project.project_id}`}
      className={`block rounded-xl border p-4 ${cfg.color} hover:opacity-90 transition-opacity`}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <div className="text-white font-semibold text-sm">{project.name}</div>
          <div className="text-gray-400 text-xs mt-0.5 capitalize">{project.facility_type}</div>
        </div>
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full whitespace-nowrap ${cfg.badge}`}>
          {cfg.label}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3 text-center">
        <div>
          <div className={`text-lg font-bold ${project.cost_exposure_usd > 500_000 ? "text-red-400" : "text-gray-200"}`}>
            {fmt_usd(project.cost_exposure_usd)}
          </div>
          <div className="text-gray-500 text-xs">exposure</div>
        </div>
        <div>
          <div className={`text-lg font-bold ${project.delay_risk_weeks >= 3 ? "text-orange-400" : project.delay_risk_weeks > 0 ? "text-yellow-400" : "text-green-400"}`}>
            {project.delay_risk_weeks > 0 ? `${project.delay_risk_weeks.toFixed(1)}w` : "0"}
          </div>
          <div className="text-gray-500 text-xs">delay risk</div>
        </div>
        <div>
          <div className={`text-lg font-bold ${project.fgi_approval_probability != null && project.fgi_approval_probability >= 80 ? "text-green-400" : project.fgi_approval_probability != null && project.fgi_approval_probability >= 65 ? "text-yellow-400" : "text-red-400"}`}>
            {project.fgi_approval_probability != null
              ? `${project.fgi_approval_probability.toFixed(0)}%`
              : "—"}
          </div>
          <div className="text-gray-500 text-xs">FGI approval</div>
        </div>
      </div>

      {(project.critical_violations > 0 || project.high_violations > 0) && (
        <div className="mt-3 flex items-center gap-2 text-xs text-gray-400">
          <AlertTriangle size={12} className="text-red-400 shrink-0" />
          {project.critical_violations > 0 && (
            <span className="text-red-400 font-medium">{project.critical_violations} critical</span>
          )}
          {project.critical_violations > 0 && project.high_violations > 0 && <span>·</span>}
          {project.high_violations > 0 && (
            <span className="text-orange-400">{project.high_violations} high</span>
          )}
          <span className="ml-auto text-gray-600 flex items-center gap-0.5">
            View <ChevronRight size={11} />
          </span>
        </div>
      )}
    </Link>
  );
}

export default function PortfolioRiskPage() {
  const [portfolio, setPortfolio] = useState<PortfolioRiskStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPortfolioRisk()
      .then(setPortfolio)
      .catch(() => setPortfolio(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="text-gray-400 text-sm">Loading portfolio risk data...</div>
      </div>
    );
  }

  if (!portfolio || portfolio.total_projects_analyzed === 0) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <h1 className="text-2xl font-bold text-white mb-2">Portfolio Risk View</h1>
        <p className="text-gray-400 text-sm mb-8">Organization-wide construction risk intelligence</p>
        <div className="card text-center py-16">
          <Upload size={40} className="text-gray-700 mx-auto mb-4" />
          <p className="text-gray-400 text-sm mb-2">No analyzed projects yet.</p>
          <p className="text-gray-600 text-xs mb-6 max-w-sm mx-auto">
            Upload blueprints to generate risk assessments. Your portfolio risk dashboard
            will show financial exposure, delay risk, and approval probability across all projects.
          </p>
          <Link href="/upload" className="btn-primary inline-flex items-center gap-2">
            <Upload size={15} />
            Analyze your first blueprint
          </Link>
        </div>
      </div>
    );
  }

  const highRiskProjects = portfolio.top_risk_projects.filter(
    (p) => p.risk_tier === "very_high" || p.risk_tier === "high"
  );

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Portfolio Risk View</h1>
          <p className="text-gray-400 text-sm mt-1">
            Organization-wide construction risk intelligence · {portfolio.total_projects_analyzed} projects analyzed
          </p>
        </div>
        <Link href="/upload" className="btn-primary flex items-center gap-2">
          <Upload size={15} />
          Add Project
        </Link>
      </div>

      {/* Portfolio KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="card border border-red-900/40">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign size={16} className="text-red-400" />
            <span className="text-gray-400 text-xs font-medium uppercase tracking-wider">Total Capital at Risk</span>
          </div>
          <div className="text-4xl font-bold text-red-400 my-2">
            {fmt_usd(portfolio.total_cost_exposure_usd)}
          </div>
          <p className="text-gray-500 text-xs">
            Estimated correction costs if all outstanding violations require redesign
          </p>
        </div>

        <div className="card border border-orange-900/40">
          <div className="flex items-center gap-2 mb-1">
            <Clock size={16} className="text-orange-400" />
            <span className="text-gray-400 text-xs font-medium uppercase tracking-wider">Total Schedule Exposure</span>
          </div>
          <div className="text-4xl font-bold text-orange-400 my-2">
            {portfolio.total_delay_risk_weeks.toFixed(0)}
            <span className="text-xl font-normal text-gray-400 ml-1">weeks</span>
          </div>
          <p className="text-gray-500 text-xs">
            Estimated delay risk across all active projects with open violations
          </p>
        </div>

        <div className="card border border-yellow-900/40">
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle size={16} className="text-yellow-400" />
            <span className="text-gray-400 text-xs font-medium uppercase tracking-wider">High-Risk Projects</span>
          </div>
          <div className="text-4xl font-bold text-yellow-400 my-2">
            {portfolio.high_risk_count}
            <span className="text-xl font-normal text-gray-400 ml-1">/ {portfolio.total_projects_analyzed}</span>
          </div>
          <p className="text-gray-500 text-xs">
            Projects with readiness score below 65 — require action before submission
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top risk projects */}
        <div className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-white font-semibold">High-Priority Projects</h2>
            <Link href="/projects" className="text-blue-400 text-sm hover:text-blue-300 flex items-center gap-1">
              All projects <ChevronRight size={14} />
            </Link>
          </div>

          {highRiskProjects.length === 0 ? (
            <div className="card text-center py-10">
              <ShieldCheck size={32} className="text-green-500 mx-auto mb-3" />
              <p className="text-green-400 font-semibold text-sm">No high-risk projects</p>
              <p className="text-gray-500 text-xs mt-1">All analyzed projects are in good shape.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {highRiskProjects.map((p) => (
                <ProjectRiskCard key={p.project_id} project={p} />
              ))}
            </div>
          )}
        </div>

        {/* Risk tier breakdown */}
        <div className="space-y-4">
          <div className="card">
            <h3 className="text-white font-semibold text-sm mb-4">Risk Tier Distribution</h3>
            <div className="space-y-3">
              {(["very_high", "high", "medium", "low"] as const).map((tier) => {
                const count = portfolio.risk_tier_counts[tier] ?? 0;
                const exposure = portfolio.risk_tier_exposure_usd[tier] ?? 0;
                const total = portfolio.total_projects_analyzed || 1;
                const pct = Math.round((count / total) * 100);
                const cfg = TIER_CONFIG[tier];
                return (
                  <div key={tier}>
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
                        <span className="text-gray-300">{cfg.label}</span>
                      </div>
                      <span className="text-gray-400">
                        {count} · {fmt_usd(exposure)}
                      </span>
                    </div>
                    <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full ${cfg.bar} rounded-full transition-all`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <div className="text-right text-xs text-gray-600 mt-0.5">{pct}%</div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="card">
            <h3 className="text-white font-semibold text-sm mb-3">Actions</h3>
            <div className="space-y-2">
              <Link href="/simulate" className="flex items-center gap-2 text-sm text-gray-300 hover:text-white p-2 rounded-lg hover:bg-gray-800 transition-colors">
                <TrendingUp size={14} className="text-green-400" />
                Run risk simulator
              </Link>
              <Link href="/upload" className="flex items-center gap-2 text-sm text-gray-300 hover:text-white p-2 rounded-lg hover:bg-gray-800 transition-colors">
                <Upload size={14} className="text-blue-400" />
                Add new blueprint
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
