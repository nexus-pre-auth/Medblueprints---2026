"use client";

import { useCallback, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { submitBlueprint, getJobStatus } from "@/lib/api";
import type { Job } from "@/lib/api";
import { Upload, FileImage, AlertCircle, CheckCircle, Loader2 } from "lucide-react";

const STAGE_LABELS: Record<string, string> = {
  ingestion: "Processing file",
  cv_parsing: "Detecting rooms (Computer Vision)",
  facility_graph: "Building facility graph",
  compliance_analysis: "Running compliance analysis",
  approval_prediction: "Predicting approval probability",
  ar_visualization: "Generating AR visualization",
  error: "Error",
};

const ACCEPTED_TYPES = [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".pdf", ".dxf"];

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [facilityType, setFacilityType] = useState("hospital");
  const [projectName, setProjectName] = useState("");
  const [useDemo, setUseDemo] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Poll job status
  useEffect(() => {
    if (!jobId || !job || job.status === "completed" || job.status === "failed") return;
    const interval = setInterval(async () => {
      try {
        const updated = await getJobStatus(jobId);
        setJob(updated);
        if (updated.status === "completed") {
          clearInterval(interval);
          router.push(`/projects/${updated.project_id}/result?job=${jobId}`);
        }
        if (updated.status === "failed") {
          clearInterval(interval);
          setError(updated.error ?? "Analysis failed");
        }
      } catch {
        clearInterval(interval);
      }
    }, 1500);
    return () => clearInterval(interval);
  }, [jobId, job, router]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!useDemo && !file) { setError("Select a file or enable demo mode"); return; }
    setError(null);
    setSubmitting(true);
    try {
      const { job_id, project_id } = await submitBlueprint(file, facilityType, undefined, useDemo);
      setJobId(job_id);
      const initial = await getJobStatus(job_id);
      setJob(initial);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-2">Upload Blueprint</h1>
      <p className="text-gray-400 text-sm mb-8">
        Upload a healthcare facility blueprint to run the full AI compliance analysis pipeline.
      </p>

      {!job ? (
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Drop zone */}
          <div
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            className={`border-2 border-dashed rounded-xl p-12 text-center transition-colors ${
              file ? "border-blue-500 bg-blue-950/20" : "border-gray-700 hover:border-gray-500"
            } ${useDemo ? "opacity-40 pointer-events-none" : ""}`}
          >
            {file ? (
              <>
                <FileImage size={40} className="text-blue-400 mx-auto mb-3" />
                <p className="text-white font-medium">{file.name}</p>
                <p className="text-gray-400 text-sm mt-1">{(file.size / 1024).toFixed(0)} KB</p>
                <button
                  type="button"
                  onClick={() => setFile(null)}
                  className="mt-3 text-xs text-gray-500 hover:text-red-400"
                >
                  Remove
                </button>
              </>
            ) : (
              <>
                <Upload size={40} className="text-gray-600 mx-auto mb-3" />
                <p className="text-gray-300 font-medium">Drop blueprint here</p>
                <p className="text-gray-500 text-sm mt-1">
                  {ACCEPTED_TYPES.join(", ")} supported
                </p>
                <label className="mt-4 btn-secondary inline-flex items-center gap-2 cursor-pointer text-sm">
                  Browse files
                  <input
                    type="file"
                    accept={ACCEPTED_TYPES.join(",")}
                    className="hidden"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  />
                </label>
              </>
            )}
          </div>

          {/* Demo mode toggle */}
          <label className="flex items-center gap-3 cursor-pointer p-4 bg-gray-900 border border-gray-800 rounded-xl">
            <input
              type="checkbox"
              checked={useDemo}
              onChange={(e) => { setUseDemo(e.target.checked); if (e.target.checked) setFile(null); }}
              className="w-4 h-4 accent-blue-500"
            />
            <div>
              <span className="text-white text-sm font-medium">Use demo blueprint</span>
              <p className="text-gray-400 text-xs mt-0.5">Try the full pipeline with a synthetic hospital floor plan</p>
            </div>
          </label>

          {/* Facility type */}
          <div>
            <label className="block text-gray-400 text-xs font-medium uppercase tracking-wider mb-2">
              Facility Type
            </label>
            <select
              value={facilityType}
              onChange={(e) => setFacilityType(e.target.value)}
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500"
            >
              {["hospital", "ambulatory_surgery_center", "clinic", "psychiatric", "rehabilitation", "long_term_care"].map((t) => (
                <option key={t} value={t}>{t.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}</option>
              ))}
            </select>
          </div>

          {error && (
            <div className="flex items-start gap-2 p-4 bg-red-950/40 border border-red-800 rounded-xl text-red-400 text-sm">
              <AlertCircle size={16} className="shrink-0 mt-0.5" />
              {error}
            </div>
          )}

          <button type="submit" disabled={submitting} className="btn-primary w-full flex items-center justify-center gap-2">
            {submitting ? <><Loader2 size={16} className="animate-spin" /> Starting analysis...</> : "Run AI Analysis"}
          </button>
        </form>
      ) : (
        /* Progress view */
        <div className="card space-y-6">
          <div className="flex items-center gap-3">
            {job.status === "completed" ? (
              <CheckCircle size={24} className="text-green-400" />
            ) : job.status === "failed" ? (
              <AlertCircle size={24} className="text-red-400" />
            ) : (
              <Loader2 size={24} className="animate-spin text-blue-400" />
            )}
            <div>
              <p className="text-white font-semibold capitalize">{job.status}</p>
              <p className="text-gray-400 text-sm">{STAGE_LABELS[job.stage ?? ""] ?? job.stage ?? "Initializing..."}</p>
            </div>
          </div>

          {/* Progress bar */}
          <div className="progress-bar">
            <div
              className="progress-fill bg-blue-500"
              style={{ width: `${job.progress_pct}%` }}
            />
          </div>
          <p className="text-gray-400 text-sm text-right">{job.progress_pct.toFixed(0)}%</p>

          {/* Pipeline stages */}
          <div className="space-y-2">
            {Object.entries(STAGE_LABELS).filter(([k]) => k !== "error").map(([stage, label]) => {
              const stages = ["ingestion", "cv_parsing", "facility_graph", "compliance_analysis", "approval_prediction", "ar_visualization"];
              const currentIdx = stages.indexOf(job.stage ?? "");
              const thisIdx = stages.indexOf(stage);
              const done = currentIdx > thisIdx || job.status === "completed";
              const active = currentIdx === thisIdx;

              return (
                <div key={stage} className={`flex items-center gap-2 text-sm ${done ? "text-green-400" : active ? "text-blue-400" : "text-gray-600"}`}>
                  <div className={`w-1.5 h-1.5 rounded-full ${done ? "bg-green-400" : active ? "bg-blue-400 animate-pulse" : "bg-gray-700"}`} />
                  {label}
                </div>
              );
            })}
          </div>

          {job.status === "failed" && (
            <div className="p-3 bg-red-950/40 border border-red-800 rounded-lg text-red-400 text-sm">
              {job.error ?? "Analysis failed"}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
