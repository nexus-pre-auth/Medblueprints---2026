"use client";

import { Settings, Key, Database, Cloud, Shield, ExternalLink } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function SettingsPage() {
  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="flex items-center gap-3 mb-2">
        <Settings size={24} className="text-gray-400" />
        <h1 className="text-2xl font-bold text-white">Settings</h1>
      </div>
      <p className="text-gray-400 text-sm mb-8">
        Platform configuration and integration status.
      </p>

      {/* API connection */}
      <div className="card mb-4">
        <div className="flex items-center gap-2 mb-4">
          <Cloud size={16} className="text-blue-400" />
          <h2 className="text-white font-semibold">API Connection</h2>
        </div>
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">Backend URL</span>
            <span className="text-gray-200 font-mono text-xs">{API_URL}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">API Docs</span>
            <a
              href={`${API_URL}/docs`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300 flex items-center gap-1 text-xs"
            >
              {API_URL}/docs <ExternalLink size={11} />
            </a>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">Health check</span>
            <a
              href={`${API_URL}/health`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300 flex items-center gap-1 text-xs"
            >
              {API_URL}/health <ExternalLink size={11} />
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
            API key auth is <strong className="text-white">off by default</strong>. Set{" "}
            <code className="bg-gray-900 px-1.5 py-0.5 rounded text-xs text-gray-200">REQUIRE_API_KEY=true</code> in your
            backend <code className="bg-gray-900 px-1.5 py-0.5 rounded text-xs text-gray-200">.env</code> to enforce it.
          </p>
          <p className="text-xs text-gray-500">
            Pass the key via <code className="text-gray-400">X-API-Key</code> header.
            Default demo key:{" "}
            <code className="bg-gray-900 px-1.5 py-0.5 rounded text-xs text-gray-300">demo-medblueprints-2026</code>
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
              sqlite+aiosqlite:///./medblueprints.db
            </code>
          </div>
          <div className="flex items-center justify-between">
            <span>Production</span>
            <code className="bg-gray-900 px-1.5 py-0.5 rounded text-xs text-gray-300">
              postgresql+asyncpg://...
            </code>
          </div>
          <p className="text-xs text-gray-500 pt-1">
            Set <code className="text-gray-400">DATABASE_URL</code> in your{" "}
            <code className="text-gray-400">.env</code> file. Tables are created automatically on startup.
          </p>
        </div>
      </div>

      {/* AI / LLM */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <Shield size={16} className="text-green-400" />
          <h2 className="text-white font-semibold">AI Configuration</h2>
        </div>
        <div className="space-y-3 text-sm text-gray-400">
          <div className="flex items-center justify-between">
            <span>Claude model</span>
            <code className="bg-gray-900 px-1.5 py-0.5 rounded text-xs text-gray-300">
              claude-opus-4-6
            </code>
          </div>
          <div className="flex items-center justify-between">
            <span>Embeddings model</span>
            <code className="bg-gray-900 px-1.5 py-0.5 rounded text-xs text-gray-300">
              all-MiniLM-L6-v2
            </code>
          </div>
          <p className="text-xs text-gray-500 pt-1">
            Set <code className="text-gray-400">ANTHROPIC_API_KEY</code> to enable LLM compliance reasoning (Layer 4).
            Demo mode works without an API key.
          </p>
        </div>
      </div>
    </div>
  );
}
