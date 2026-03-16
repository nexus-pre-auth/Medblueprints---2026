"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Upload,
  ClipboardCheck,
  ShieldAlert,
  Database,
  Settings,
  Layers,
  BarChart3,
} from "lucide-react";

const nav = [
  { href: "/dashboard",  label: "Risk Dashboard",    icon: LayoutDashboard },
  { href: "/portfolio",  label: "Portfolio Risk",    icon: BarChart3 },
  { href: "/upload",     label: "Analyze Blueprint", icon: Upload },
  { href: "/projects",   label: "Projects",          icon: Layers },
  { href: "/compliance", label: "Regulatory Rules",  icon: ClipboardCheck },
  { href: "/simulate",   label: "Risk Simulator",    icon: ShieldAlert },
  { href: "/dataset",    label: "Dataset & Moat",    icon: Database },
  { href: "/settings",   label: "Settings",          icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-60 bg-gray-900 border-r border-gray-800 flex flex-col h-screen sticky top-0">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">M</div>
          <span className="font-bold text-white text-sm tracking-tight">MedBlueprints</span>
        </div>
        <p className="text-gray-500 text-xs mt-1">Construction Risk Intelligence</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                active
                  ? "bg-blue-600 text-white"
                  : "text-gray-400 hover:text-gray-100 hover:bg-gray-800"
              }`}
            >
              <Icon size={16} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-gray-800">
        <p className="text-gray-600 text-xs">v1.0.0 · Claude-powered</p>
      </div>
    </aside>
  );
}
