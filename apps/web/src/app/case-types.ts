export type CaseStatus = "active" | "archived" | "closed";
export type EntityType = "domain" | "url";
export type Confidence = "high" | "medium" | "low" | "unknown";

export type CaseSummary = {
  id: string;
  title: string;
  objective: string;
  scope_category: string;
  scope_notes: string;
  case_type: string;
  status: CaseStatus;
  scope_acknowledged: boolean;
  scope_acknowledged_at: string;
  tags: string[];
  analyst_notes: string;
  created_at: string;
  updated_at: string;
  entity_count: number;
};

export type EntityRecord = {
  id: string;
  case_id: string;
  type: EntityType;
  value: string;
  display_name: string;
  description: string;
  confidence: Confidence;
  tags: string[];
  notes: string;
  created_at: string;
  updated_at: string;
};

export type EnrichmentModuleStatus = "success" | "failed" | "skipped";
export type EnrichmentRunStatus = "success" | "partial" | "failed";

export type EnrichmentModuleResult = {
  module_name: string;
  status: EnrichmentModuleStatus;
  started_at: string;
  completed_at: string;
  result: Record<string, unknown>;
  error_message: string;
};

export type EnrichmentRunRecord = {
  id: string;
  case_id: string;
  entity_id: string;
  module_name: string;
  status: EnrichmentRunStatus;
  started_at: string;
  completed_at: string;
  results: EnrichmentModuleResult[];
  error_message: string;
  created_at: string;
};

export type NewsReviewStatus = "pending" | "relevant" | "not_relevant";
export type NewsRunStatus = "success" | "partial" | "failed";
export type TrendGroupType = "keyword" | "classification" | "source" | "time_window" | "theme";

export type NewsKeywordSet = {
  id: string;
  case_id: string;
  name: string;
  keywords: string[];
  scope_notes: string;
  created_at: string;
  updated_at: string;
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

export type NewsIngestionRunRecord = {
  id: string;
  case_id: string;
  keyword_set_id: string | null;
  provider: string;
  status: NewsRunStatus;
  started_at: string;
  completed_at: string;
  query_keywords: string[];
  result_count: number;
  error_message: string;
  created_at: string;
  results: NewsResultRecord[];
};

export type EvidenceLinkRecord = {
  id: string;
  case_id: string;
  news_result_id: string;
  source_url: string;
  publisher: string;
  title: string;
  snippet: string;
  published_at: string;
  retrieved_at: string;
  query_keyword: string;
  analyst_note: string;
  created_at: string;
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

export type CaseFormState = {
  title: string;
  objective: string;
  scopeCategory: string;
  scopeNotes: string;
  caseType: string;
  status: CaseStatus;
  tags: string;
  analystNotes: string;
  scopeAcknowledged: boolean;
};

export type EntityFormState = {
  type: EntityType;
  value: string;
  displayName: string;
  description: string;
  confidence: Confidence;
  tags: string;
  notes: string;
};

export type KeywordSetFormState = {
  name: string;
  keywords: string;
  scopeNotes: string;
};

export const emptyCreateCase: CaseFormState = {
  title: "",
  objective: "",
  scopeCategory: "Vendor review",
  scopeNotes: "Passive public-source review only.",
  caseType: "Vendor risk snapshot",
  status: "active",
  tags: "",
  analystNotes: "",
  scopeAcknowledged: false,
};

export const emptyKeywordSet: KeywordSetFormState = {
  name: "Scam and fraud monitoring",
  keywords: "scam alert, fraud warning, impersonation scam",
  scopeNotes: "Scoped public news and search monitoring only.",
};

export const emptyEntity: EntityFormState = {
  type: "domain",
  value: "",
  displayName: "",
  description: "",
  confidence: "unknown",
  tags: "",
  notes: "",
};

export function tagsFromInput(value: string): string[] {
  const tags = value
    .split(",")
    .map((tag) => tag.trim().toLowerCase())
    .filter(Boolean);

  return Array.from(new Set(tags));
}

export function tagsToInput(tags: string[]): string {
  return tags.join(", ");
}

export function keywordsFromInput(value: string): string[] {
  const keywords = value
    .split(",")
    .map((keyword) => keyword.trim().toLowerCase())
    .filter(Boolean);

  return Array.from(new Set(keywords));
}

export function draftFromCase(caseRecord: CaseSummary): CaseFormState {
  return {
    title: caseRecord.title,
    objective: caseRecord.objective,
    scopeCategory: caseRecord.scope_category,
    scopeNotes: caseRecord.scope_notes,
    caseType: caseRecord.case_type,
    status: caseRecord.status,
    tags: tagsToInput(caseRecord.tags),
    analystNotes: caseRecord.analyst_notes,
    scopeAcknowledged: caseRecord.scope_acknowledged,
  };
}

export function draftFromEntity(entity: EntityRecord): EntityFormState {
  return {
    type: entity.type,
    value: entity.value,
    displayName: entity.display_name,
    description: entity.description,
    confidence: entity.confidence,
    tags: tagsToInput(entity.tags),
    notes: entity.notes,
  };
}
