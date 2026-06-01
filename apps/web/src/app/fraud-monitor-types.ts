export type ProviderStatus = "ready" | "missing_config" | "unsupported" | "timeout" | "partial_success";
export type ValidationSeverity = "error" | "warning" | "info";
export type NewsReviewStatus = "pending" | "relevant" | "not_relevant";
export type NewsRunStatus = "success" | "partial" | "failed";
export type TrendGroupType = "keyword" | "classification" | "source" | "time_window" | "theme";
export type EvidenceFilter = "all" | "saved" | "unsaved";
export type ResultSort =
  | "retrieved_desc"
  | "retrieved_asc"
  | "published_desc"
  | "published_asc"
  | "title_asc"
  | "source_asc"
  | "review_asc";

export type ProviderInfo = {
  name: string;
  status: ProviderStatus;
  note: string;
  request_limit: string;
  timeout_seconds: number;
  last_run_status: NewsRunStatus | "";
  last_result_count: number;
  last_error_message: string;
  next_retry_at: string;
};

export type ConfigurationIssue = {
  severity: ValidationSeverity;
  provider: string;
  message: string;
};

export type FraudMonitorConfigurationValidation = {
  is_valid: boolean;
  fixture_mode: boolean;
  provider_count: number;
  ready_provider_count: number;
  issues: ConfigurationIssue[];
  recommendations: string[];
};

export type FraudMonitorSchedule = {
  enabled: boolean;
  interval_minutes: number;
  next_run_at: string;
  last_started_at: string;
  last_completed_at: string;
  updated_at: string;
};

export type FraudMonitorRuntime = {
  is_running: boolean;
  ready_provider_count: number;
  last_error_message: string;
  last_error_at: string;
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
  provider_run_summaries: FraudMonitorProviderRunSummary[];
};

export type FraudMonitorProviderRunSummary = {
  provider: string;
  status: NewsRunStatus;
  raw_result_count: number;
  stored_result_count: number;
  filtered_result_count: number;
  note: string;
};

export type NewsResultRecord = {
  id: string;
  case_id: string;
  run_id: string;
  provider: string;
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
  evidence_analyst_note: string;
  seen_count: number;
  duplicate_count: number;
  theme: string;
  classification_label: string;
  classification_basis: "title" | "snippet" | "fallback";
  classification_terms: string[];
  fraud_state_code: string;
  fraud_state_label: string;
  fraud_state_basis: "title" | "snippet" | "publisher" | "source_url" | "unknown";
  fraud_state_terms: string[];
  source_quality: "named_source" | "unnamed_source";
  recency_cue: "fresh" | "recent" | "older" | "unknown";
  prioritization_cue: string;
  created_at: string;
};

export type FraudMonitorResultPage = {
  total_matching: number;
  limit: number;
  offset: number;
  has_next: boolean;
  has_previous: boolean;
  search: string;
  sort: ResultSort;
  review_filter: NewsReviewStatus | "all";
  provider_filter: string;
  evidence_filter: EvidenceFilter;
};

export type TrendGroup = {
  group_type: TrendGroupType;
  label: string;
  result_count: number;
  sample_titles: string[];
  source_attribution: string[];
  priority_cue: string;
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
  configuration_validation: FraudMonitorConfigurationValidation;
  schedule: FraudMonitorSchedule;
  latest_job: FraudMonitorJob | null;
  jobs: FraudMonitorJob[];
  results: NewsResultRecord[];
  result_page: FraudMonitorResultPage;
  evidence_count: number;
  runtime: FraudMonitorRuntime;
  trend_summary: TrendSummary;
  total_results: number;
  pending_results: number;
  relevant_results: number;
  not_relevant_results: number;
};
