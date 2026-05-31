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
  evidence_count: 0,
  trend_summary: {
    case_id: "",
    generated_at: "",
    groups: [],
  },
  total_results: 0,
  pending_results: 0,
  relevant_results: 0,
  not_relevant_results: 0,
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
