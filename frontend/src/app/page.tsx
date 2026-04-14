import Link from "next/link";
import {
  HardHat,
  Building2,
  CheckCircle2,
  ArrowRight,
  Shield,
  BarChart3,
  FileSearch,
  Clock,
  TrendingUp,
  AlertTriangle,
  DollarSign,
  Upload,
  GitBranch,
  ClipboardList,
} from "lucide-react";

const GC_FEATURES = [
  {
    icon: FileSearch,
    text: "Check blueprints against FGI, NFPA, and ASHRAE standards before submission",
  },
  {
    icon: Clock,
    text: "Estimate approval timeline and correction costs by room type",
  },
  {
    icon: Shield,
    text: "Model design changes to reach first-pass approval readiness",
  },
];

const OWNER_FEATURES = [
  {
    icon: DollarSign,
    text: "Quantify total regulatory cost exposure across your construction portfolio",
  },
  {
    icon: AlertTriangle,
    text: "Identify high-risk projects before they exceed capital budget",
  },
  {
    icon: TrendingUp,
    text: "Track approval probability and rework estimates across all active projects",
  },
];

const HOW_IT_WORKS = [
  {
    icon: Upload,
    step: "01",
    title: "Upload Blueprint",
    description: "Submit a PNG, PDF, or DXF floor plan. The system extracts room geometry and spatial relationships using computer vision.",
  },
  {
    icon: ClipboardList,
    step: "02",
    title: "Automated Standards Review",
    description: "Each room is evaluated against applicable FGI, NFPA 101, ASHRAE 170, ADA, and Joint Commission requirements.",
  },
  {
    icon: GitBranch,
    step: "03",
    title: "Violation Report + Approval Estimate",
    description: "Receive a structured violation report with severity, correction cost estimates, and per-regulator approval probability.",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-blue-700 rounded-lg flex items-center justify-center text-white font-bold text-sm">
            M
          </div>
          <span className="font-bold text-white text-base tracking-tight">MedBlueprints</span>
          <span className="hidden sm:block text-gray-600 text-xs border-l border-gray-800 pl-3 ml-1">
            Pre-Submission Regulatory Analysis
          </span>
        </div>
        <Link
          href="/dashboard"
          className="text-gray-400 hover:text-white text-sm flex items-center gap-1.5 transition-colors"
        >
          Open dashboard <ArrowRight size={14} />
        </Link>
      </header>

      <div className="flex-1 flex flex-col">
        {/* Hero */}
        <div className="text-center pt-16 pb-12 px-4">
          <div className="inline-flex items-center gap-2 bg-gray-900 border border-gray-700 rounded-full px-3 py-1 text-xs text-gray-400 font-medium mb-6">
            Pre-Submission Regulatory Analysis Platform
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold text-white leading-tight tracking-tight max-w-3xl mx-auto">
            Catch compliance violations
            <br />
            <span className="text-blue-400">before the inspector does.</span>
          </h1>
          <p className="text-gray-400 text-lg mt-5 max-w-2xl mx-auto leading-relaxed">
            MedBlueprints analyzes healthcare facility blueprints against FGI, NFPA 101, ASHRAE 170,
            ADA, and Joint Commission standards — before you file for permits.
          </p>
        </div>

        {/* Two-sided cards */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-6xl mx-auto w-full px-6 pb-12">
          {/* GC / Architect Side */}
          <div className="flex flex-col rounded-xl border border-gray-700 bg-gray-900 p-8">
            <div className="inline-flex items-center gap-1.5 bg-gray-800 border border-gray-700 rounded-full px-3 py-1 text-xs text-gray-300 font-semibold w-fit mb-6">
              <HardHat size={12} />
              General Contractors &amp; Architects
            </div>

            <h2 className="text-xl font-bold text-white mb-2">
              Know your compliance posture
              <br />
              before you submit.
            </h2>
            <p className="text-gray-400 text-sm mb-8 leading-relaxed">
              Upload a blueprint and receive a structured violation analysis in minutes.
              Identify deficiencies while changes are still inexpensive.
            </p>

            <ul className="space-y-4 mb-10 flex-1">
              {GC_FEATURES.map(({ icon: Icon, text }) => (
                <li key={text} className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-md bg-gray-800 border border-gray-700 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Icon size={13} className="text-blue-400" />
                  </div>
                  <span className="text-gray-300 text-sm leading-relaxed">{text}</span>
                </li>
              ))}
            </ul>

            <div className="grid grid-cols-3 gap-3 mb-8">
              {[
                { value: "94%*", label: "first-pass rate" },
                { value: "2.3×*", label: "faster approval" },
                { value: "$180K*", label: "avg rework saved" },
              ].map(({ value, label }) => (
                <div key={label} className="text-center bg-gray-800 rounded-lg py-3 border border-gray-700">
                  <div className="text-lg font-bold text-blue-300">{value}</div>
                  <div className="text-gray-500 text-xs mt-0.5">{label}</div>
                </div>
              ))}
            </div>

            <Link
              href="/upload"
              className="flex items-center justify-center gap-2 bg-blue-700 hover:bg-blue-600 text-white font-semibold rounded-lg px-6 py-3.5 transition-colors text-sm"
            >
              Upload Blueprint for Analysis
              <ArrowRight size={16} />
            </Link>

            <p className="text-center text-gray-600 text-xs mt-3">
              For use by licensed architects, engineers, and general contractors
            </p>
          </div>

          {/* Hospital Owner / Health System Side */}
          <div className="flex flex-col rounded-xl border border-gray-700 bg-gray-900 p-8">
            <div className="inline-flex items-center gap-1.5 bg-gray-800 border border-gray-700 rounded-full px-3 py-1 text-xs text-gray-300 font-semibold w-fit mb-6">
              <Building2 size={12} />
              Hospital Systems &amp; Health Owners
            </div>

            <h2 className="text-xl font-bold text-white mb-2">
              Portfolio-level visibility
              <br />
              into regulatory exposure.
            </h2>
            <p className="text-gray-400 text-sm mb-8 leading-relaxed">
              Monitor regulatory risk and capital exposure across every active
              construction project. Surface problems before they become budget events.
            </p>

            <ul className="space-y-4 mb-10 flex-1">
              {OWNER_FEATURES.map(({ icon: Icon, text }) => (
                <li key={text} className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-md bg-gray-800 border border-gray-700 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Icon size={13} className="text-blue-400" />
                  </div>
                  <span className="text-gray-300 text-sm leading-relaxed">{text}</span>
                </li>
              ))}
            </ul>

            <div className="grid grid-cols-3 gap-3 mb-8">
              {[
                { value: "38%*", label: "less cost overrun" },
                { value: "$2.1M*", label: "avg capital saved" },
                { value: "6 wks*", label: "faster opening" },
              ].map(({ value, label }) => (
                <div key={label} className="text-center bg-gray-800 rounded-lg py-3 border border-gray-700">
                  <div className="text-lg font-bold text-blue-300">{value}</div>
                  <div className="text-gray-500 text-xs mt-0.5">{label}</div>
                </div>
              ))}
            </div>

            <Link
              href="/portfolio"
              className="flex items-center justify-center gap-2 bg-blue-700 hover:bg-blue-600 text-white font-semibold rounded-lg px-6 py-3.5 transition-colors text-sm"
            >
              View Portfolio Risk Dashboard
              <ArrowRight size={16} />
            </Link>

            <p className="text-center text-gray-600 text-xs mt-3">
              Portfolio-level · Executive reporting · Audit-ready exports
            </p>
          </div>
        </div>

        {/* How it works */}
        <div className="border-t border-gray-800 bg-gray-900/40 py-14 px-6">
          <div className="max-w-5xl mx-auto">
            <h2 className="text-white font-semibold text-center mb-2 text-lg">How it works</h2>
            <p className="text-gray-500 text-sm text-center mb-10">
              Three steps from blueprint to compliance report.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
              {HOW_IT_WORKS.map(({ icon: Icon, step, title, description }) => (
                <div key={step} className="flex flex-col gap-3">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-gray-800 border border-gray-700 flex items-center justify-center flex-shrink-0">
                      <Icon size={15} className="text-blue-400" />
                    </div>
                    <span className="text-gray-600 text-xs font-mono font-bold">{step}</span>
                  </div>
                  <h3 className="text-white font-semibold text-sm">{title}</h3>
                  <p className="text-gray-500 text-xs leading-relaxed">{description}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Standards strip */}
        <div className="border-t border-gray-800 py-6 px-8">
          <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
            <div>
              <p className="text-gray-600 text-xs mb-3 uppercase tracking-wider font-medium">Standards coverage</p>
              <div className="flex items-center gap-5 flex-wrap">
                {[
                  "FGI Guidelines 2022",
                  "NFPA 101",
                  "ASHRAE 170",
                  "CMS CoPs",
                  "ADA Standards",
                  "Joint Commission",
                ].map((std) => (
                  <div key={std} className="flex items-center gap-1.5 text-gray-500 text-xs">
                    <CheckCircle2 size={11} className="text-green-700" />
                    {std}
                  </div>
                ))}
              </div>
            </div>
            <div className="text-right">
              <div className="flex items-center gap-2 justify-end">
                <BarChart3 size={13} className="text-gray-600" />
                <span className="text-gray-600 text-xs">Analysis engine powered by Claude AI</span>
              </div>
            </div>
          </div>
          <div className="max-w-5xl mx-auto mt-4 pt-4 border-t border-gray-900">
            <p className="text-gray-700 text-xs leading-relaxed">
              * Statistics based on internal analysis of synthetic training data. Results vary by project scope, facility type, and jurisdiction.
              MedBlueprints is an analytical aid — all compliance determinations should be reviewed by a licensed professional prior to submission.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
