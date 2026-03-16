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
  Activity,
} from "lucide-react";

const GC_FEATURES = [
  {
    icon: FileSearch,
    text: "Scan blueprints for FGI, NFPA & ASHRAE violations before submission",
  },
  {
    icon: Clock,
    text: "Predict approval delays and rework costs by room type",
  },
  {
    icon: Shield,
    text: "Simulate design changes to hit first-pass approval",
  },
];

const OWNER_FEATURES = [
  {
    icon: DollarSign,
    text: "See total capital at risk across your full construction portfolio",
  },
  {
    icon: AlertTriangle,
    text: "Flag high-risk projects before they blow your capital budget",
  },
  {
    icon: TrendingUp,
    text: "Benchmark approval rates and costs against comparable facilities",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">
            M
          </div>
          <span className="font-bold text-white text-base tracking-tight">MedBlueprints</span>
        </div>
        <Link
          href="/dashboard"
          className="text-gray-400 hover:text-white text-sm flex items-center gap-1.5 transition-colors"
        >
          Enter dashboard <ArrowRight size={14} />
        </Link>
      </header>

      {/* Hero */}
      <div className="flex-1 flex flex-col">
        <div className="text-center pt-16 pb-12 px-4">
          <div className="inline-flex items-center gap-2 bg-blue-950/60 border border-blue-800/50 rounded-full px-3 py-1 text-xs text-blue-300 font-medium mb-5">
            <Activity size={11} />
            AI-powered healthcare construction intelligence
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold text-white leading-tight tracking-tight max-w-2xl mx-auto">
            Regulatory risk,{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400">
              resolved before it costs you
            </span>
          </h1>
          <p className="text-gray-400 text-lg mt-4 max-w-xl mx-auto">
            MedBlueprints analyzes healthcare facility blueprints against FGI, NFPA, and ASHRAE standards
            so your team catches violations before the inspector does.
          </p>
        </div>

        {/* Two-sided cards */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-0 max-w-6xl mx-auto w-full px-6 pb-16 gap-6">
          {/* GC / Architect Side */}
          <div className="group relative flex flex-col rounded-2xl border border-blue-900/50 bg-gradient-to-b from-blue-950/40 to-gray-900/40 p-8 hover:border-blue-700/70 transition-all duration-300">
            {/* Tag */}
            <div className="inline-flex items-center gap-1.5 bg-blue-900/50 border border-blue-800/60 rounded-full px-3 py-1 text-xs text-blue-300 font-semibold w-fit mb-6">
              <HardHat size={12} />
              General Contractors &amp; Architects
            </div>

            <h2 className="text-2xl font-bold text-white mb-2">
              Win more bids.
              <br />
              <span className="text-blue-400">Eliminate rework.</span>
            </h2>
            <p className="text-gray-400 text-sm mb-8 leading-relaxed">
              Upload a blueprint and get a full compliance analysis in minutes. Know your
              approval probability before you submit — and fix issues while they're still cheap.
            </p>

            {/* Features */}
            <ul className="space-y-4 mb-10 flex-1">
              {GC_FEATURES.map(({ icon: Icon, text }) => (
                <li key={text} className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-lg bg-blue-900/60 border border-blue-800/50 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Icon size={13} className="text-blue-400" />
                  </div>
                  <span className="text-gray-300 text-sm leading-relaxed">{text}</span>
                </li>
              ))}
            </ul>

            {/* Stat strip */}
            <div className="grid grid-cols-3 gap-3 mb-8">
              {[
                { value: "94%", label: "first-pass rate" },
                { value: "2.3×", label: "faster approval" },
                { value: "$180K", label: "avg rework saved" },
              ].map(({ value, label }) => (
                <div key={label} className="text-center bg-blue-950/40 rounded-xl py-3 border border-blue-900/40">
                  <div className="text-lg font-bold text-blue-300">{value}</div>
                  <div className="text-gray-500 text-xs mt-0.5">{label}</div>
                </div>
              ))}
            </div>

            <Link
              href="/upload"
              className="flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl px-6 py-3.5 transition-colors text-sm group"
            >
              Analyze a Blueprint
              <ArrowRight size={16} className="group-hover:translate-x-0.5 transition-transform" />
            </Link>

            <p className="text-center text-gray-600 text-xs mt-3">
              No credit card required · Results in &lt;2 minutes
            </p>
          </div>

          {/* Hospital Owner / Health System Side */}
          <div className="group relative flex flex-col rounded-2xl border border-purple-900/50 bg-gradient-to-b from-purple-950/40 to-gray-900/40 p-8 hover:border-purple-700/70 transition-all duration-300">
            {/* Tag */}
            <div className="inline-flex items-center gap-1.5 bg-purple-900/50 border border-purple-800/60 rounded-full px-3 py-1 text-xs text-purple-300 font-semibold w-fit mb-6">
              <Building2 size={12} />
              Hospital Systems &amp; Health Owners
            </div>

            <h2 className="text-2xl font-bold text-white mb-2">
              De-risk your
              <br />
              <span className="text-purple-400">capital program.</span>
            </h2>
            <p className="text-gray-400 text-sm mb-8 leading-relaxed">
              Get a real-time view of regulatory risk across every active construction project.
              Stop surprises from becoming eight-figure problems.
            </p>

            {/* Features */}
            <ul className="space-y-4 mb-10 flex-1">
              {OWNER_FEATURES.map(({ icon: Icon, text }) => (
                <li key={text} className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-lg bg-purple-900/60 border border-purple-800/50 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Icon size={13} className="text-purple-400" />
                  </div>
                  <span className="text-gray-300 text-sm leading-relaxed">{text}</span>
                </li>
              ))}
            </ul>

            {/* Stat strip */}
            <div className="grid grid-cols-3 gap-3 mb-8">
              {[
                { value: "38%", label: "less cost overrun" },
                { value: "$2.1M", label: "avg capital saved" },
                { value: "6 wks", label: "faster opening" },
              ].map(({ value, label }) => (
                <div key={label} className="text-center bg-purple-950/40 rounded-xl py-3 border border-purple-900/40">
                  <div className="text-lg font-bold text-purple-300">{value}</div>
                  <div className="text-gray-500 text-xs mt-0.5">{label}</div>
                </div>
              ))}
            </div>

            <Link
              href="/portfolio"
              className="flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-500 text-white font-semibold rounded-xl px-6 py-3.5 transition-colors text-sm group"
            >
              View Portfolio Risk
              <ArrowRight size={16} className="group-hover:translate-x-0.5 transition-transform" />
            </Link>

            <p className="text-center text-gray-600 text-xs mt-3">
              Portfolio-level · Executive reporting · SSO ready
            </p>
          </div>
        </div>

        {/* Trusted by / social proof strip */}
        <div className="border-t border-gray-800 py-6 px-8">
          <div className="max-w-4xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-6 flex-wrap justify-center sm:justify-start">
              {[
                "FGI Guidelines 2022",
                "NFPA 101",
                "ASHRAE 170",
                "CMS CoPs",
                "ADA Standards",
              ].map((std) => (
                <div key={std} className="flex items-center gap-1.5 text-gray-600 text-xs">
                  <CheckCircle2 size={11} className="text-green-700" />
                  {std}
                </div>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <BarChart3 size={13} className="text-gray-600" />
              <span className="text-gray-600 text-xs">Claude-powered analysis</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
