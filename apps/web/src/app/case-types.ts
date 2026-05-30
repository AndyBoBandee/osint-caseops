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
