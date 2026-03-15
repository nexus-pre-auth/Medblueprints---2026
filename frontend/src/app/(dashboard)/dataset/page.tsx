"use client";

import { useEffect, useState } from "react";
import { getOutcomeStats, getDesignIntelligence, getGraphStats } from "@/lib/api";
import { Database, TrendingUp, AlertTriangle, CheckCircle, Lock } from "lucide-react";

export default function DatasetPage() {
  const [stats, setStats] = useState<Record<string, number> | null>(null);
  const [intelligence, setIntelligence] = useState<Record<string, unknown> | null>(null);
  const [graphStats, setGraphStats] = useState<Record<string, number> | null>(null);

  useEffect(() => {
    Promise.all([
      getOutcomeStats().catch(() => null),
      getDesignIntelligence().catch(() => null),
      getGraphStats().catch(() => null),
    ]).then(([s, i, g]) => {
      setStats(s as Record<string, number>);
      setIntelligence(i as Record<string, unknown>);
      setGraphStats(g as Record<string, number>);
    });
  }, []);

  const moatProgress = Math.min(100, ((stats?.labeled_projects ?? 0) / 50) * 100);

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-2">
        <Database size={24} className="text-purple-400" />
        <h1 className="text-2xl font-bold text-white">Dataset & Strategic Moat</h1>
      </div>
      <p className="text-gray-400 text-sm mb-8">
        Every project run through MedBlueprints contributes to a proprietary dataset of healthcare
        facility design decisions and regulatory outcomes. This becomes impossible for competitors to replicate.
      </p>

      {/* Moat progress */}
      <div className="card mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Lock size={16} className="text-purple-400" />
          <h2 className="text-white font-semibold">Moat Progress</h2>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6 text-center">
          <div>
            <div className="text-3xl font-bold text-white">{stats?.total_projects ?? 0}</div>
            <div className="text-xs text-gray-500 mt-1">Total projects</div>
          </div>
          <div>
            <div className="text-3xl font-bold text-purple-400">{stats?.labeled_projects ?? 0}</div>
            <div className="text-xs text-gray-500 mt-1">Labeled outcomes</div>
          </div>
          <div>
            <div className="text-3xl font-bold text-green-400">{stats?.approved_projects ?? 0}</div>
            <div className="text-xs text-gray-500 mt-1">Approved</div>
          </div>
          <div>
            <div className="text-3xl font-bold text-white">{stats?.approval_rate_pct ?? 0}%</div>
            <div className="text-xs text-gray-500 mt-1">Approval rate</div>
          </div>
        </div>

        <div className="mb-2 flex justify-between text-sm">
          <span className="text-gray-400">Model training threshold</span>
          <span className={stats?.model_training_ready ? "text-green-400" : "text-yellow-400"}>
            {stats?.labeled_projects ?? 0} / 50 labeled projects
          </span>
        </div>
        <div className="progress-bar">
          <div
            className={`progress-fill ${moatProgress >= 100 ? "bg-green-500" : "bg-purple-500"}`}
            style={{ width: `${moatProgress}%` }}
          />
        </div>
        {stats?.model_training_ready ? (
          <div className="mt-3 flex items-center gap-2 text-green-400 text-sm">
            <CheckCircle size={14} />
            Model training ready — use /api/v1/predictions/model/train to retrain
          </div>
        ) : (
          <p className="mt-3 text-gray-500 text-xs">
            Collect {50 - (stats?.labeled_projects ?? 0)} more labeled outcomes to enable model retraining.
          </p>
        )}
      </div>

      {/* Regulatory Design Graph */}
      <div className="card mb-6">
        <h2 className="text-white font-semibold mb-4">Regulatory Design Graph</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
          {[
            ["Total nodes", graphStats?.total_nodes ?? 0, "text-white"],
            ["Total edges", graphStats?.total_edges ?? 0, "text-white"],
            ["Projects", graphStats?.projects ?? 0, "text-blue-400"],
            ["Violation relationships", graphStats?.violation_relationships ?? 0, "text-red-400"],
          ].map(([label, value, cls]) => (
            <div key={String(label)}>
              <div className={`text-2xl font-bold ${cls}`}>{value}</div>
              <div className="text-xs text-gray-500 mt-1">{label}</div>
            </div>
          ))}
        </div>
        <p className="mt-4 text-gray-500 text-xs">
          Neo4j status: {graphStats?.neo4j_connected ? "✓ Connected" : "○ Using in-memory graph (enable USE_NEO4J=true for production)"}
        </p>
      </div>

      {/* Design Intelligence */}
      {intelligence && (
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={16} className="text-green-400" />
            <h2 className="text-white font-semibold">Design Intelligence Query Results</h2>
          </div>

          {(intelligence.projects_analyzed as number) === 0 ? (
            <div className="text-gray-500 text-sm">
              No outcome data yet. Submit projects and record approval outcomes to unlock design intelligence.
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-gray-400 text-sm">
                Analysis across <strong className="text-white">{intelligence.projects_analyzed as number}</strong> projects ·{" "}
                Approval rate: <strong className="text-white">{intelligence.approval_rate_pct as number}%</strong>
              </p>

              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-green-950/20 border border-green-900 rounded-lg">
                  <div className="text-green-400 text-sm font-medium mb-2 flex items-center gap-1">
                    <CheckCircle size={12} /> Approved Projects
                  </div>
                  <div className="text-white text-sm">
                    Count: {(intelligence.approved as Record<string, number>)?.count ?? 0}
                  </div>
                  <div className="text-gray-400 text-xs mt-1">
                    Avg critical violations: {(intelligence.approved as Record<string, number>)?.avg_critical_violations ?? "—"}
                  </div>
                  <div className="text-gray-400 text-xs">
                    Avg review: {(intelligence.approved as Record<string, number>)?.avg_review_days ?? "—"} days
                  </div>
                </div>
                <div className="p-4 bg-red-950/20 border border-red-900 rounded-lg">
                  <div className="text-red-400 text-sm font-medium mb-2 flex items-center gap-1">
                    <AlertTriangle size={12} /> Rejected Projects
                  </div>
                  <div className="text-white text-sm">
                    Count: {(intelligence.rejected as Record<string, number>)?.count ?? 0}
                  </div>
                  <div className="text-gray-400 text-xs mt-1">
                    Avg critical violations: {(intelligence.rejected as Record<string, number>)?.avg_critical_violations ?? "—"}
                  </div>
                  <div className="text-gray-400 text-xs">
                    Avg rework cost: ${(intelligence.rejected as Record<string, number>)?.avg_rework_cost_usd?.toLocaleString() ?? "—"}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
