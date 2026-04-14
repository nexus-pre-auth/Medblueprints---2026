"use client";

import { Settings, Key, Database, Cpu, Cloud, ExternalLink } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function SettingsPage() {
  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="flex items-center gap-3 mb-2">
        <Settings size={24} className="text-gray-400" />
        <h1 className="text-2xl font-bold text-white">Platform Configuration</h1>
      </div>
      <p className="text-gray-400 text-sm mb-8">
        Integration status and system configuration. Contact your administrator to modify settings.
      </p>

      {/* API connection */}
      <div className="card mb-4">
        <div className="flex items-center gap-2 mb-4">
          <Cloud size={16} className="text-blue-400" />
          <h2 className="text-white font-semibold">API Connection</h2>
        </div>
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">Backend endpoint</span>
            <span className="text-gray-200 font-mono text-xs">{API_URL}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">API reference</span>
            <a
              href={`${API_URL}/docs`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300 flex items-center gap-1 text-xs"
            >
              Open API docs <ExternalLink size={11} />
            </a>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">Health status</span>
            <a
              href={`${API_URL}/health`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300 flex items-center gap-1 text-xs"
            >
              Check status <ExternalLink size={11} />
            </a>
          </div>
        </div>
      </div>

      {/* Auth */}
      <div className="card mb-4">
        <div className="flex items-center gap-2 mb-4">
          <Key size={16} className="text-yellow-400" />
          <h2 className="text-white font-semibold">Authentication</h2>
        </div>
        <div className="space-y-2 text-sm text-gray-400">
          <p>
            API key authentication is configured via environment variable.
            Pass credentials using the{" "}
            <code className="bg-gray-900 px-1.5 py-0.5 rounded text-xs text-gray-200">X-API-Key</code>{" "}
            request header.
          </p>
          <p className="text-xs text-gray-500 pt-1">
            Contact your administrator to provision or rotate API keys.
            Set{" "}
            <code className="text-gray-400">REQUIRE_API_KEY=true</code>{" "}
            in the server environment to enforce authentication on all endpoints.
          </p>
        </div>
      </div>

      {/* Database */}
      <div className="card mb-4">
        <div className="flex items-center gap-2 mb-4">
          <Database size={16} className="text-purple-400" />
          <h2 className="text-white font-semibold">Database</h2>
        </div>
        <div className="space-y-2 text-sm text-gray-400">
          <div className="flex items-center justify-between">
            <span>Development</span>
            <code className="bg-gray-900 px-1.5 py-0.5 rounded text-xs text-gray-300">
              SQLite (local)
            </code>
          </div>
          <div className="flex items-center justify-between">
            <span>Production</span>
            <code className="bg-gray-900 px-1.5 py-0.5 rounded text-xs text-gray-300">
              PostgreSQL 16
            </code>
          </div>
          <p className="text-xs text-gray-500 pt-1">
            Configure via{" "}
            <code className="text-gray-400">DATABASE_URL</code>{" "}
            environment variable. Schema is created automatically on startup.
          </p>
        </div>
      </div>

      {/* Analysis engine */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <Cpu size={16} className="text-green-400" />
          <h2 className="text-white font-semibold">Analysis Engine</h2>
        </div>
        <div className="space-y-3 text-sm text-gray-400">
          <div className="flex items-center justify-between">
            <span>Standards reviewed</span>
            <span className="text-gray-300 text-xs">FGI · NFPA · ASHRAE · ADA · Joint Commission</span>
          </div>
          <div className="flex items-center justify-between">
            <span>LLM reasoning model</span>
            <code className="bg-gray-900 px-1.5 py-0.5 rounded text-xs text-gray-300">
              Claude (Anthropic)
            </code>
          </div>
          <div className="flex items-center justify-between">
            <span>Semantic search</span>
            <code className="bg-gray-900 px-1.5 py-0.5 rounded text-xs text-gray-300">
              FAISS + sentence-transformers
            </code>
          </div>
          <div className="flex items-center justify-between">
            <span>Approval prediction</span>
            <code className="bg-gray-900 px-1.5 py-0.5 rounded text-xs text-gray-300">
              XGBoost classifier
            </code>
          </div>
          <p className="text-xs text-gray-500 pt-1">
            Set{" "}
            <code className="text-gray-400">ANTHROPIC_API_KEY</code>{" "}
            to enable LLM compliance reasoning. All other layers function without an API key.
          </p>
        </div>
      </div>
    </div>
  );
}
