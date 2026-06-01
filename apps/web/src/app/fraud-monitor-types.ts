export type ProviderStatus = "ready" | "missing_config" | "unsupported" | "timeout" | "partial_success";
export type ValidationSeverity = "error" | "warning" | "info";
export type NewsReviewStatus = "pending" | "relevant" | "not_relevant";
export type NewsRunStatus = "success" | "partial" | "failed";
export type FindingConfidence = "high" | "medium" | "low" | "unknown";
export type FindingStatus = "draft" | "active" | "resolved" | "archived";
export type TimelineEventType =
  | "scan_run"
  | "review_update"
  | "evidence_save"
  | "evidence_update"
  | "finding_create"
  | "finding_update"
  | "export_generation";
export type TrendGroupType = "keyword" | "classification" | "source" | "time_window" | "theme";
export type EvidenceFilter = "all" | "saved" | "unsaved";
export type EvidenceArtifactType = "source_url" | "html_snapshot" | "text_snapshot" | "screenshot";
export type EvidenceArtifactAvailability = "available" | "not_captured";
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
  evidence_artifacts: EvidenceArtifactRecord[];
  available_artifact_count: number;
  vault_state: "not_saved" | "metadata_only" | "artifacts_available";
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

export type EvidenceArtifactRecord = {
  id: string;
  case_id: string;
  evidence_link_id: string;
  news_result_id: string;
  artifact_type: EvidenceArtifactType;
  display_name: string;
  storage_path: string;
  media_type: string;
  byte_size: number;
  content_hash: string;
  source_url: string;
  captured_at: string;
  retention_policy: string;
  availability: EvidenceArtifactAvailability;
  capture_note: string;
  created_at: string;
};

export type LinkedEvidenceRecord = {
  id: string;
  source_url: string;
  publisher: string;
  title: string;
  analyst_note: string;
  review_status: NewsReviewStatus;
  available_artifact_count: number;
  created_at: string;
};

export type FindingRecord = {
  id: string;
  case_id: string;
  title: string;
  summary: string;
  confidence: FindingConfidence;
  status: FindingStatus;
  analyst_notes: string;
  linked_evidence: LinkedEvidenceRecord[];
  created_at: string;
  updated_at: string;
};

export type TimelineEventRecord = {
  id: string;
  case_id: string;
  event_type: TimelineEventType;
  title: string;
  summary: string;
  actor: string;
  related_result_id: string | null;
  related_evidence_link_id: string | null;
  related_finding_id: string | null;
  metadata: Record<string, unknown>;
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

export type OperationsDataDirectoryHealth = {
  status: "ok" | "warning" | "error";
  path: string;
  exists: boolean;
  writable: boolean;
  file_count: number;
  byte_size: number;
};

export type OperationsDatabaseHealth = {
  status: "ok" | "warning" | "error";
  path: string;
  exists: boolean;
  byte_size: number;
  case_count: number;
  result_count: number;
  evidence_count: number;
  job_count: number;
  checked_at: string;
};

export type OperationsSchedulerHealth = {
  status: "idle" | "running" | "disabled";
  enabled: boolean;
  task_active: boolean;
  job_running: boolean;
  interval_minutes: number;
  next_run_at: string;
  last_completed_at: string;
};

export type OperationsWarning = {
  severity: ValidationSeverity;
  message: string;
};

export type OperationsBackupArtifact = {
  filename: string;
  path: string;
  byte_size: number;
  created_at: string;
  includes: string[];
  download_url: string;
};

export type OperationsRetentionCandidate = {
  id: string;
  filename: string;
  path: string;
  reason: string;
  byte_size: number;
  created_at: string;
};

export type OperationsStatus = {
  generated_at: string;
  local_only: boolean;
  data_directory: OperationsDataDirectoryHealth;
  database: OperationsDatabaseHealth;
  scheduler: OperationsSchedulerHealth;
  warnings: OperationsWarning[];
  backups: OperationsBackupArtifact[];
  retention_candidates: OperationsRetentionCandidate[];
};

export type FraudMonitorDashboardData = {
  keyword: string;
  case_id: string;
  providers: ProviderInfo[];
  detailed_provider: ProviderInfo;
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
  findings: FindingRecord[];
  timeline_events: TimelineEventRecord[];
  operations: OperationsStatus;
};
