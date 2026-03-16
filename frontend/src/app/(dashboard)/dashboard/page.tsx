"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getDashboardStats,
  listProjects,
  getPortfolioRisk,
} from "@/lib/api";
import type { Project, PortfolioRiskStats } from "@/lib/api";
import {
  AlertTriangle,
  DollarSign,
  Clock,
  TrendingDown,
  Upload,
  ArrowRight,
  ShieldAlert,
  BarChart3,
} from "lucide-react";

interface DashboardStats {
  total_projects: number;
  analyzed_projects: number;
  approved_projects: number;
  avg_submission_readiness: number;
  avg_critical_violations: number;
}

function fmt_usd(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

function RiskTierBadge({ tier }: { tier: string }) {
  const map: Record<string, string> = {
    very_high: "bg-red-900/60 text-red-300 border border-red-700",
    high: "bg-orange-900/60 text-orange-300 border border-orange-700",
    medium: "bg-yellow-900/60 text-yellow-300 border border-yellow-700",
    low: "bg-green-900/60 text-green-300 border border-green-700",
    unknown: "bg-gray-800 text-gray-500",
  };
  const label: Record<string, string> = {
    very_high: "Very High",
    high: "High",
    medium: "Medium",
    low: "Low",
    unknown: "—",
  };
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${map[tier] ?? map.unknown}`}>
      {label[tier] ?? tier}
    </span>
  );
}

function deriveRiskTier(score: number | null | undefined): string {
  if (score == null) return "unknown";
  if (score >= 85) return "low";
  if (score >= 65) return "medium";
  if (score >= 40) return "high";
  return "very_high";
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioRiskStats | null>(null);

  useEffect(() => {
    Promise.all([
      getDashboardStats().catch(() => null),
      listProjects({}).catch(() => ({ projects: [] })),
      getPortfolioRisk().catch(() => null),
    ]).then(([s, p, port]) => {
      setStats(s as DashboardStats);
      setProjects((p as { projects: Project[] }).projects.slice(0, 8));
      setPortfolio(port as PortfolioRiskStats);
    });
  }, []);

  const highRisk = portfolio?.high_risk_count ?? 0;
  const costExposure = portfolio?.total_cost_exposure_usd ?? 0;
  const delayWeeks = portfolio?.total_delay_risk_weeks ?? 0;
  const readiness = stats?.avg_submission_readiness ?? 0;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Executive Risk Dashboard</h1>
          <p className="text-gray-400 text-sm mt-1">
            Construction risk intelligence across your portfolio
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/portfolio" className="btn-secondary flex items-center gap-2 text-sm">
            <BarChart3 size={15} />
            Portfolio View
          </Link>
          <Link href="/upload" className="btn-primary flex items-center gap-2">
            <Upload size={16} />
            Analyze Blueprint
          </Link>
        </div>
      </div>

      {/* Executive KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="card border border-red-900/40">
          <div className="flex items-center gap-2 mb-2">
            <DollarSign size={15} className="text-red-400" />
            <span className="text-gray-400 text-xs font-medium uppercase tracking-wider">Capital at Risk</span>
          </div>
          <div className="text-3xl font-bold text-red-400">{fmt_usd(costExposure)}</div>
          <div className="text-gray-500 text-xs mt-1">total correction exposure</div>
        </div>

        <div className="card border border-orange-900/40">
          <div className="flex items-center gap-2 mb-2">
            <ShieldAlert size={15} className="text-orange-400" />
            <span className="text-gray-400 text-xs font-medium uppercase tracking-wider">High-Risk Projects</span>
          </div>
          <div className="text-3xl font-bold text-orange-400">{highRisk}</div>
          <div className="text-gray-500 text-xs mt-1">
            of {stats?.total_projects ?? "—"} total analyzed
          </div>
        </div>

        <div className="card border border-yellow-900/40">
          <div className="flex items-center gap-2 mb-2">
            <Clock size={15} className="text-yellow-400" />
            <span className="text-gray-400 text-xs font-medium uppercase tracking-wider">Delay Risk</span>
          </div>
          <div className="text-3xl font-bold text-yellow-400">
            {delayWeeks.toFixed(0)}
            <span className="text-base font-normal text-gray-400 ml-1">wks</span>
          </div>
          <div className="text-gray-500 text-xs mt-1">estimated schedule exposure</div>
        </div>

        <div className="card">
          <div className="flex items-center gap-2 mb-2">
            <TrendingDown size={15} className="text-blue-400" />
            <span className="text-gray-400 text-xs font-medium uppercase tracking-wider">Avg Readiness</span>
          </div>
          <div className={`text-3xl font-bold ${readiness >= 85 ? "text-green-400" : readiness >= 65 ? "text-yellow-400" : "text-red-400"}`}>
            {readiness > 0 ? readiness.toFixed(0) : "—"}
            {readiness > 0 && <span className="text-base font-normal text-gray-400">/100</span>}
          </div>
          <div className="text-gray-500 text-xs mt-1">submission readiness score</div>
        </div>
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Project risk table */}
        <div className="lg:col-span-2 card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-white font-semibold">Projects — Risk Overview</h2>
            <Link href="/projects" className="text-blue-400 text-sm hover:text-blue-300 flex items-center gap-1">
              View all <ArrowRight size={14} />
            </Link>
          </div>

          {projects.length === 0 ? (
            <div className="text-center py-12">
              <Upload size={32} className="text-gray-700 mx-auto mb-3" />
              <p className="text-gray-500 text-sm">No projects yet. Upload a blueprint to generate your first risk assessment.</p>
              <Link href="/upload" className="btn-primary inline-flex items-center gap-2 mt-4 text-sm">
                Upload blueprint
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800">
                    <th className="text-left pb-3 font-medium">Project</th>
                    <th className="text-left pb-3 font-medium">Risk</th>
                    <th className="text-right pb-3 font-medium">Cost Exposure</th>
                    <th className="text-right pb-3 font-medium">Delay</th>
                    <th className="text-right pb-3 font-medium">FGI %</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {projects.map((p) => {
                    const tier = deriveRiskTier(p.metrics.submission_readiness_score);
                    const delay =
                      (p.metrics.critical_violations ?? 0) * 1.5 +
                      (p.metrics.high_violations ?? 0) * 0.5;
                    return (
                      <tr key={p.project_id} className="hover:bg-gray-800/50 transition-colors">
                        <td className="py-3">
                          <Link href={`/projects/${p.project_id}`} className="text-white hover:text-blue-400 font-medium">
                            {p.name}
                          </Link>
                          <div className="text-gray-500 text-xs mt-0.5">{p.facility_type}</div>
                        </td>
                        <td className="py-3">
                          <RiskTierBadge tier={tier} />
                        </td>
                        <td className="py-3 text-right">
                          {p.metrics.estimated_correction_cost_usd != null ? (
                            <span className={p.metrics.estimated_correction_cost_usd > 500_000 ? "text-red-400 font-semibold" : "text-gray-300"}>
                              {fmt_usd(p.metrics.estimated_correction_cost_usd)}
                            </span>
                          ) : (
                            <span className="text-gray-600">—</span>
                          )}
                        </td>
                        <td className="py-3 text-right">
                          {delay > 0 ? (
                            <span className={delay >= 3 ? "text-orange-400 font-medium" : "text-gray-400"}>
                              {delay.toFixed(1)}w
                            </span>
                          ) : (
                            <span className="text-green-500 text-xs">none</span>
                          )}
                        </td>
                        <td className="py-3 text-right text-gray-300">
                          {p.metrics.fgi_approval_probability != null
                            ? `${p.metrics.fgi_approval_probability.toFixed(0)}%`
                            : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right column */}
        <div className="space-y-4">
          <div className="card">
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle size={16} className="text-orange-400" />
              <h3 className="text-white font-semibold text-sm">Portfolio Risk Breakdown</h3>
            </div>
            {portfolio ? (
              <div className="space-y-2">
                {(["very_high", "high", "medium", "low"] as const).map((tier) => {
                  const count = portfolio.risk_tier_counts[tier] ?? 0;
                  const exposure = portfolio.risk_tier_exposure_usd[tier] ?? 0;
                  const total = portfolio.total_projects_analyzed || 1;
                  const pct = Math.round((count / total) * 100);
                  const barColor =
                    tier === "very_high" ? "bg-red-500" :
                    tier === "high" ? "bg-orange-500" :
                    tier === "medium" ? "bg-yellow-500" : "bg-green-500";
                  const label = { very_high: "Very High", high: "High", medium: "Medium", low: "Low" }[tier];
                  return (
                    <div key={tier}>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-gray-400">{label}</span>
                        <span className="text-gray-300 font-medium">
                          {count} {count === 1 ? "project" : "projects"} · {fmt_usd(exposure)}
                        </span>
                      </div>
                      <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                        <div className={`h-full ${barColor} rounded-full`} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-gray-600 text-sm">No data yet. Analyze your first blueprint.</div>
            )}
            <Link href="/portfolio" className="mt-4 text-orange-400 text-xs flex items-center gap-1 hover:text-orange-300">
              Full portfolio view <ArrowRight size={12} />
            </Link>
          </div>

          <div className="card">
            <h3 className="text-white font-semibold text-sm mb-3">Risk Intelligence Actions</h3>
            <div className="space-y-2">
              <Link href="/upload" className="flex items-center gap-2 text-sm text-gray-300 hover:text-white p-2 rounded-lg hover:bg-gray-800 transition-colors">
                <Upload size={14} className="text-blue-400" />
                Analyze new blueprint
              </Link>
              <Link href="/simulate" className="flex items-center gap-2 text-sm text-gray-300 hover:text-white p-2 rounded-lg hover:bg-gray-800 transition-colors">
                <ShieldAlert size={14} className="text-orange-400" />
                Run risk simulator
              </Link>
              <Link href="/portfolio" className="flex items-center gap-2 text-sm text-gray-300 hover:text-white p-2 rounded-lg hover:bg-gray-800 transition-colors">
                <BarChart3 size={14} className="text-purple-400" />
                Portfolio risk view
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
