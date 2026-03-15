/**
 * MedBlueprints API Client
 * Typed wrappers around all backend endpoints.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_V1 = `${API_BASE}/api/v1`;

// ── Types ──────────────────────────────────────────────────────────────

export type JobStatus = "pending" | "processing" | "completed" | "failed";

export interface Job {
  job_id: string;
  project_id: string;
  status: JobStatus;
  stage: string | null;
  filename: string | null;
  progress_pct: number;
  created_at: string;
  updated_at: string;
  error: string | null;
  has_result: boolean;
}

export interface ComplianceViolation {
  violation_id: string;
  rule_id: string;
  room_id: string;
  room_label: string;
  severity: "critical" | "high" | "medium" | "low" | "advisory";
  constraint_type: string;
  description: string;
  actual_value: number | null;
  required_value: number | null;
  unit: string | null;
  estimated_correction_cost_usd: number | null;
  remediation_suggestion: string | null;
  source: string;
}

export interface RoomComplianceResult {
  room_id: string;
  room_label: string;
  room_type: string;
  violations: ComplianceViolation[];
  passed_rules: string[];
  llm_interpretation: string | null;
}

export interface ComplianceReport {
  project_id: string;
  room_results: RoomComplianceResult[];
  total_violations: number;
  critical_violations: number;
  high_violations: number;
  medium_violations: number;
  low_violations: number;
  estimated_total_correction_cost_usd: number;
  overall_compliant: boolean;
  summary: string | null;
}

export interface RegulatorPrediction {
  regulator: string;
  approval_probability: number;
  expected_review_days: number;
  primary_concerns: string[];
}

export interface ApprovalPrediction {
  project_id: string;
  submission_readiness_score: number;
  overall_risk_level: "low" | "medium" | "high" | "very_high";
  regulator_predictions: RegulatorPrediction[];
  top_blocking_issues: string[];
  recommended_actions: string[];
  estimated_rework_cost_usd: number;
  estimated_rework_days: number;
  confidence: number;
  model_version: string;
}

export interface AnalysisResult {
  project_id: string;
  parse_result: {
    rooms: Array<{
      id: string;
      label: string;
      room_type: string;
      area_sqft: number | null;
      confidence: number;
    }>;
    total_area_sqft: number | null;
    corridors: Array<{ id: string; width_ft: number | null }>;
    parse_confidence: number;
  };
  facility_graph: {
    node_count: number;
    edge_count: number;
  };
  compliance_report: ComplianceReport;
  prediction: ApprovalPrediction;
  ar_scene: Record<string, unknown>;
  ingestion_warnings: string[];
  demo_mode?: boolean;
}

export interface Project {
  project_id: string;
  name: string;
  facility_type: string;
  status: string;
  state: string | null;
  city: string | null;
  metrics: {
    total_rooms: number | null;
    total_area_sqft: number | null;
    critical_violations: number | null;
    high_violations: number | null;
    submission_readiness_score: number | null;
    fgi_approval_probability: number | null;
    estimated_correction_cost_usd: number | null;
  };
  compliance_summary: Record<string, unknown> | null;
  prediction_summary: Record<string, unknown> | null;
  outcome: {
    approval_result: string;
    regulator: string | null;
    review_duration_days: number | null;
    actual_rework_cost_usd: number | null;
  } | null;
  created_at: string;
}

// ── API Functions ──────────────────────────────────────────────────────

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Jobs ───────────────────────────────────────────────────────────────

export async function submitBlueprint(
  file: File | null,
  facilityType = "hospital",
  projectId?: string,
  useDemo = false
): Promise<{ job_id: string; project_id: string; poll_url: string }> {
  const form = new FormData();
  if (file) form.append("file", file);
  form.append("facility_type", facilityType);
  form.append("use_demo", String(useDemo));
  if (projectId) form.append("project_id", projectId);

  const res = await fetch(`${API_V1}/jobs/analyze`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getJobStatus(jobId: string): Promise<Job> {
  return apiFetch<Job>(`${API_V1}/jobs/${jobId}`);
}

export async function getJobResult(jobId: string): Promise<AnalysisResult> {
  return apiFetch<AnalysisResult>(`${API_V1}/jobs/${jobId}/result`);
}

export async function listJobs(limit = 20): Promise<{ jobs: Job[] }> {
  return apiFetch(`${API_V1}/jobs?limit=${limit}`);
}

// ── Projects ────────────────────────────────────────────────────────────

export async function createProject(data: {
  name: string;
  facility_type?: string;
  state?: string;
  city?: string;
  owner_email?: string;
  org_name?: string;
}): Promise<{ project_id: string }> {
  return apiFetch(`${API_V1}/projects`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listProjects(params?: { org?: string; status?: string }): Promise<{ projects: Project[] }> {
  const qs = new URLSearchParams(params as Record<string, string>).toString();
  return apiFetch(`${API_V1}/projects${qs ? `?${qs}` : ""}`);
}

export async function getProject(projectId: string): Promise<Project> {
  return apiFetch(`${API_V1}/projects/${projectId}`);
}

export async function getDashboardStats(): Promise<{
  total_projects: number;
  analyzed_projects: number;
  approved_projects: number;
  avg_submission_readiness: number;
  avg_critical_violations: number;
}> {
  return apiFetch(`${API_V1}/projects/dashboard`);
}

export async function recordOutcome(
  projectId: string,
  data: {
    approval_result: string;
    regulator?: string;
    review_duration_days?: number;
    actual_rework_cost_usd?: number;
  }
): Promise<void> {
  await apiFetch(`${API_V1}/projects/${projectId}/outcome`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ── Compliance & Rules ─────────────────────────────────────────────────

export async function getRuleStats(): Promise<{
  total_rules: number;
  room_types_covered: string[];
  sources: string[];
}> {
  return apiFetch(`${API_V1}/compliance/rules/stats`);
}

export async function searchRules(query: string, topK = 5) {
  return apiFetch(`${API_V1}/compliance/rules/search?q=${encodeURIComponent(query)}&top_k=${topK}`);
}

// ── Dataset Intelligence ───────────────────────────────────────────────

export async function getOutcomeStats() {
  return apiFetch(`${API_V1}/predictions/outcomes/stats`);
}

export async function getDesignIntelligence(facilityType?: string) {
  const qs = facilityType ? `?facility_type=${facilityType}` : "";
  return apiFetch(`${API_V1}/predictions/outcomes/intelligence${qs}`);
}

export async function getGraphStats() {
  return apiFetch(`${API_V1}/graph/stats`);
}
