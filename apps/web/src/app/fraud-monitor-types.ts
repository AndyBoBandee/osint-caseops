export type ProviderStatus = "ready" | "needs_key" | "unsupported";
export type NewsReviewStatus = "pending" | "relevant" | "not_relevant";
export type NewsRunStatus = "success" | "partial" | "failed";
export type TrendGroupType = "keyword" | "source" | "time_window" | "theme";

export type ProviderInfo = {
  name: string;
  status: ProviderStatus;
  note: string;
};

export type FraudMonitorSchedule = {
  enabled: boolean;
  interval_minutes: number;
  next_run_at: string;
  last_started_at: string;
  last_completed_at: string;
  updated_at: string;
};

export type FraudMonitorJob = {
  id: string;
  keyword: string;
  trigger_type: "manual" | "scheduled";
  status: NewsRunStatus;
  started_at: string;
  completed_at: string;
  provider_count: number;
  result_count: number;
  error_message: string;
  created_at: string;
  provider_runs: string[];
};

export type NewsResultRecord = {
  id: string;
  case_id: string;
  run_id: string;
  keyword: string;
  source_url: string;
  publisher: string;
  title: string;
  snippet: string;
  published_at: string;
  retrieved_at: string;
  review_status: NewsReviewStatus;
  saved_as_evidence: boolean;
  evidence_link_id: string | null;
  theme: string;
  created_at: string;
};

export type TrendGroup = {
  group_type: TrendGroupType;
  label: string;
  result_count: number;
  sample_titles: string[];
  source_attribution: string[];
  confidence_language: string;
};

export type TrendSummary = {
  case_id: string;
  generated_at: string;
  groups: TrendGroup[];
};

export type FraudMonitorDashboardData = {
  keyword: string;
  case_id: string;
  providers: ProviderInfo[];
  schedule: FraudMonitorSchedule;
  latest_job: FraudMonitorJob | null;
  jobs: FraudMonitorJob[];
  results: NewsResultRecord[];
  evidence_count: number;
  trend_summary: TrendSummary;
  total_results: number;
  pending_results: number;
  relevant_results: number;
  not_relevant_results: number;
};
