import { FraudMonitorDashboard } from "./fraud-monitor-dashboard";
import { FraudMonitorDashboardData } from "./fraud-monitor-types";

type HealthResponse = {
  status: string;
  service?: string;
};

const apiBaseUrl = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

const emptyDashboard: FraudMonitorDashboardData = {
  keyword: "fraud",
  case_id: "",
  providers: [],
  detailed_provider: {
    name: "brave",
    status: "missing_config",
    note: "Set BRAVE_SEARCH_API_KEY before using detailed search.",
    request_limit: "Brave detailed search requires local API key configuration.",
    timeout_seconds: 8,
    last_run_status: "",
    last_result_count: 0,
    last_error_message: "",
    next_retry_at: "",
  },
  configuration_validation: {
    is_valid: false,
    fixture_mode: false,
    provider_count: 0,
    ready_provider_count: 0,
    issues: [],
    recommendations: [],
  },
  schedule: {
    enabled: false,
    interval_minutes: 60,
    next_run_at: "",
    last_started_at: "",
    last_completed_at: "",
    updated_at: "",
  },
  latest_job: null,
  jobs: [],
  results: [],
  result_page: {
    total_matching: 0,
    limit: 25,
    offset: 0,
    has_next: false,
    has_previous: false,
    search: "",
    sort: "retrieved_desc",
    review_filter: "all",
    provider_filter: "all",
    evidence_filter: "all",
  },
  evidence_count: 0,
  runtime: {
    is_running: false,
    ready_provider_count: 0,
    last_error_message: "",
    last_error_at: "",
  },
  trend_summary: {
    case_id: "",
    generated_at: "",
    groups: [],
  },
  total_results: 0,
  pending_results: 0,
  relevant_results: 0,
  not_relevant_results: 0,
  findings: [],
  timeline_events: [],
  operations: {
    generated_at: "",
    local_only: true,
    data_directory: {
      status: "error",
      path: "",
      exists: false,
      writable: false,
      file_count: 0,
      byte_size: 0,
    },
    database: {
      status: "error",
      path: "",
      exists: false,
      byte_size: 0,
      case_count: 0,
      result_count: 0,
      evidence_count: 0,
      job_count: 0,
      checked_at: "",
    },
    scheduler: {
      status: "disabled",
      enabled: false,
      task_active: false,
      job_running: false,
      interval_minutes: 60,
      next_run_at: "",
      last_completed_at: "",
    },
    warnings: [],
    backups: [],
    retention_candidates: [],
  },
};

async function getApiJson<T>(path: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return fallback;
    }

    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

export default async function Home() {
  const [health, dashboard] = await Promise.all([
    getApiJson<HealthResponse>("/health", { status: "unavailable" }),
    getApiJson<FraudMonitorDashboardData>("/fraud-monitor/dashboard", emptyDashboard),
  ]);

  return (
    <FraudMonitorDashboard
      initialApiOnline={health.status === "ok"}
      initialDashboard={dashboard}
    />
  );
}
