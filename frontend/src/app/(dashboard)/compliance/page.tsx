"use client";

import { useEffect, useState, useMemo } from "react";
import { getRuleStats, searchRules } from "@/lib/api";
import { ShieldCheck, Search, Filter } from "lucide-react";

interface RuleStats {
  total_rules: number;
  room_types_covered: string[];
  sources: string[];
}

interface SearchResult {
  rules: Array<{
    rule_id: string;
    title: string;
    description: string;
    room_types: string[];
    source: string;
    severity: string;
    constraint_type: string;
    parameters: Record<string, unknown>;
  }>;
}

const SEVERITY_PILL: Record<string, string> = {
  critical: "bg-red-950/50 text-red-400 border border-red-900",
  high: "bg-orange-950/50 text-orange-400 border border-orange-900",
  medium: "bg-yellow-950/50 text-yellow-400 border border-yellow-900",
  low: "bg-blue-950/50 text-blue-400 border border-blue-900",
  advisory: "bg-gray-900 text-gray-400 border border-gray-800",
};

const SOURCE_COLORS: Record<string, string> = {
  FGI: "text-purple-400",
  NFPA: "text-red-400",
  ASHRAE: "text-blue-400",
  ADA: "text-green-400",
  "Joint Commission": "text-yellow-400",
};

export default function CompliancePage() {
  const [stats, setStats] = useState<RuleStats | null>(null);
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [results, setResults] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedSource, setSelectedSource] = useState<string>("all");
  const [selectedSeverity, setSelectedSeverity] = useState<string>("all");

  useEffect(() => {
    getRuleStats().then(setStats).catch(() => null);
    // Load initial rules
    searchRules("", 20).then((r) => setResults(r as SearchResult)).catch(() => null);
  }, []);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 350);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    if (debouncedQuery === "" && results) return; // already loaded
    setLoading(true);
    searchRules(debouncedQuery, 30)
      .then((r) => setResults(r as SearchResult))
      .catch(() => null)
      .finally(() => setLoading(false));
  }, [debouncedQuery]);

  const filteredRules = useMemo(() => {
    if (!results?.rules) return [];
    return results.rules.filter((r) => {
      if (selectedSource !== "all" && !r.source.toUpperCase().includes(selectedSource)) return false;
      if (selectedSeverity !== "all" && r.severity !== selectedSeverity) return false;
      return true;
    });
  }, [results, selectedSource, selectedSeverity]);

  const sources = stats?.sources ?? [];
  const severities = ["critical", "high", "medium", "low", "advisory"];

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-2">
        <ShieldCheck size={24} className="text-green-400" />
        <h1 className="text-2xl font-bold text-white">Compliance Rule Library</h1>
      </div>
      <p className="text-gray-400 text-sm mb-6">
        {stats?.total_rules ?? "—"} rules from FGI, NFPA, ASHRAE, ADA, and Joint Commission.
        Search by room type, rule description, or keyword.
      </p>

      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="card text-center">
            <div className="text-3xl font-bold text-white">{stats.total_rules}</div>
            <div className="text-xs text-gray-500 mt-1">Total rules</div>
          </div>
          <div className="card text-center">
            <div className="text-3xl font-bold text-blue-400">{stats.sources.length}</div>
            <div className="text-xs text-gray-500 mt-1">Regulatory sources</div>
          </div>
          <div className="card text-center">
            <div className="text-3xl font-bold text-green-400">{stats.room_types_covered.length}</div>
            <div className="text-xs text-gray-500 mt-1">Room types covered</div>
          </div>
        </div>
      )}

      {/* Search + filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search rules… e.g. 'OR ventilation', 'ADA corridor width'"
            className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-9 pr-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <Filter size={14} className="text-gray-500 shrink-0" />
          <select
            value={selectedSource}
            onChange={(e) => setSelectedSource(e.target.value)}
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
          >
            <option value="all">All sources</option>
            {sources.map((s) => (
              <option key={s} value={s.toUpperCase()}>{s}</option>
            ))}
          </select>

          <select
            value={selectedSeverity}
            onChange={(e) => setSelectedSeverity(e.target.value)}
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
          >
            <option value="all">All severities</option>
            {severities.map((s) => (
              <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Results count */}
      <div className="flex items-center justify-between mb-3">
        <p className="text-gray-500 text-xs">
          {loading ? "Searching…" : `${filteredRules.length} rules`}
          {(selectedSource !== "all" || selectedSeverity !== "all") && " (filtered)"}
        </p>
      </div>

      {/* Rule cards */}
      <div className="space-y-3">
        {filteredRules.map((rule) => (
          <div key={rule.rule_id} className="card hover:border-gray-700 transition-colors">
            <div className="flex items-start justify-between gap-4 mb-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <span className="text-white font-medium text-sm">{rule.title}</span>
                  <span className="text-gray-600 text-xs font-mono">{rule.rule_id}</span>
                </div>
                <p className="text-gray-400 text-xs leading-relaxed">{rule.description}</p>
              </div>
              <div className="flex flex-col items-end gap-1.5 shrink-0">
                <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${SEVERITY_PILL[rule.severity] ?? SEVERITY_PILL.advisory}`}>
                  {rule.severity}
                </span>
                <span className={`text-xs font-medium ${SOURCE_COLORS[rule.source] ?? "text-gray-400"}`}>
                  {rule.source}
                </span>
              </div>
            </div>

            <div className="flex flex-wrap gap-2 mt-2">
              {rule.room_types.slice(0, 6).map((rt) => (
                <span
                  key={rt}
                  className="text-xs px-2 py-0.5 bg-gray-900 border border-gray-800 text-gray-400 rounded"
                >
                  {rt.replace(/_/g, " ")}
                </span>
              ))}
              {rule.room_types.length > 6 && (
                <span className="text-xs text-gray-600">+{rule.room_types.length - 6} more</span>
              )}
            </div>

            {/* Key parameters */}
            {Object.keys(rule.parameters).length > 0 && (
              <div className="mt-2 flex flex-wrap gap-3 text-xs text-gray-500">
                {Object.entries(rule.parameters).slice(0, 4).map(([k, v]) => (
                  <span key={k}>
                    <span className="text-gray-600">{k.replace(/_/g, " ")}:</span>{" "}
                    <span className="text-gray-400">{String(v)}</span>
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}

        {filteredRules.length === 0 && !loading && (
          <div className="text-center py-12 text-gray-500 text-sm">
            No rules match your search. Try a different keyword or clear the filters.
          </div>
        )}
      </div>
    </div>
  );
}
