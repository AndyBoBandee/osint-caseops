import { FormEvent } from "react";

import {
  Confidence,
  emptyEntity,
  EnrichmentModuleResult,
  EnrichmentRunRecord,
  EntityFormState,
  EntityRecord,
  EntityType,
  CaseSummary,
} from "./case-types";

type EntityPanelProps = {
  editingEntityId: string | null;
  enrichmentLoadingId: string | null;
  enrichmentRuns: EnrichmentRunRecord[];
  entities: EntityRecord[];
  entityDraft: EntityFormState;
  entityLoading: boolean;
  selectedCase: CaseSummary | null;
  onCancelEdit: () => void;
  onDeleteEntity: (entity: EntityRecord) => void;
  onEditEntity: (entity: EntityRecord) => void;
  onEntityDraftChange: (draft: EntityFormState) => void;
  onRunEnrichment: (entity: EntityRecord) => void;
  onSaveEntity: (event: FormEvent<HTMLFormElement>) => void;
};

function confidenceBadgeClass(confidence: Confidence) {
  if (confidence === "high") {
    return "oc-badge oc-badge-high";
  }

  if (confidence === "medium") {
    return "oc-badge oc-badge-medium";
  }

  return "oc-badge oc-badge-low";
}

function runBadgeClass(status: EnrichmentRunRecord["status"]) {
  if (status === "success") {
    return "oc-badge oc-badge-success";
  }

  if (status === "partial") {
    return "oc-badge oc-badge-medium";
  }

  return "oc-badge oc-badge-danger";
}

function moduleBadgeClass(status: EnrichmentModuleResult["status"]) {
  if (status === "success") {
    return "oc-badge oc-badge-success";
  }

  if (status === "skipped") {
    return "oc-badge oc-badge-muted";
  }

  return "oc-badge oc-badge-danger";
}

function formatModuleName(moduleName: string) {
  return moduleName.replaceAll("_", " ");
}

function resultValueToText(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => resultValueToText(item)).join(", ");
  }

  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }

  return String(value ?? "");
}

function summarizeModuleResult(moduleResult: EnrichmentModuleResult) {
  if (moduleResult.status === "failed") {
    return moduleResult.error_message || "Module failed.";
  }

  const result = moduleResult.result;
  if (moduleResult.module_name === "dns_lookup" && Array.isArray(result.addresses)) {
    return `${result.addresses.length} address${result.addresses.length === 1 ? "" : "es"}`;
  }

  if (moduleResult.module_name === "http_status" && "status_code" in result) {
    return `HTTP ${resultValueToText(result.status_code)}`;
  }

  if (moduleResult.module_name === "redirect_chain" && "redirect_count" in result) {
    return `${resultValueToText(result.redirect_count)} redirect(s)`;
  }

  if (moduleResult.module_name === "page_title" && result.title) {
    return resultValueToText(result.title);
  }

  if (moduleResult.module_name === "security_headers" && Array.isArray(result.missing)) {
    return `${result.missing.length} missing header${result.missing.length === 1 ? "" : "s"}`;
  }

  if ("available" in result) {
    return result.available ? "Available" : "Not found";
  }

  const firstEntry = Object.entries(result)[0];
  return firstEntry ? resultValueToText(firstEntry[1]) : "No details returned.";
}

export function EntityPanel({
  editingEntityId,
  enrichmentLoadingId,
  enrichmentRuns,
  entities,
  entityDraft,
  entityLoading,
  selectedCase,
  onCancelEdit,
  onDeleteEntity,
  onEditEntity,
  onEntityDraftChange,
  onRunEnrichment,
  onSaveEntity,
}: EntityPanelProps) {
  const focusedEntity =
    entities.find((entity) => entity.id === editingEntityId) ?? entities[0] ?? null;
  const latestRunByEntity = new Map<string, EnrichmentRunRecord>();

  for (const run of enrichmentRuns) {
    if (!latestRunByEntity.has(run.entity_id)) {
      latestRunByEntity.set(run.entity_id, run);
    }
  }

  const focusedRun = focusedEntity ? latestRunByEntity.get(focusedEntity.id) ?? null : null;

  return (
    <section className="oc-card" id="entity-profile" aria-label="Entities">
      <div className="oc-card-header">
        <div>
          <h2 className="oc-card-title">Entity profile</h2>
          <p className="oc-card-description">{selectedCase ? selectedCase.title : "Select a case"}</p>
        </div>
      </div>

      {selectedCase ? (
        <>
          {focusedEntity ? (
            <div className="oc-panel">
              <div className="oc-entity-header">
                <div>
                  <div className="oc-entity-value oc-technical">{focusedEntity.value}</div>
                  <div className="oc-case-meta">
                    <span className="oc-badge oc-badge-info">{focusedEntity.type}</span>
                    <span className={confidenceBadgeClass(focusedEntity.confidence)}>
                      {focusedEntity.confidence} confidence
                    </span>
                  </div>
                </div>
                <button
                  className="oc-btn oc-btn-primary"
                  disabled={enrichmentLoadingId === focusedEntity.id}
                  onClick={() => onRunEnrichment(focusedEntity)}
                  type="button"
                >
                  {enrichmentLoadingId === focusedEntity.id ? "Running" : "Run enrichment"}
                </button>
              </div>
              <div className="oc-profile-grid">
                <div className="oc-definition-list">
                  <div className="oc-definition-row">
                    <span className="oc-definition-term">Summary</span>
                    <span className="oc-definition-value">
                      {focusedEntity.description || "No enrichment summary has been added yet."}
                    </span>
                  </div>
                  <div className="oc-definition-row">
                    <span className="oc-definition-term">Evidence</span>
                    <span className="oc-definition-value">
                      Evidence can be linked as case capture support in the viewer below.
                    </span>
                  </div>
                  <div className="oc-definition-row">
                    <span className="oc-definition-term">Notes</span>
                    <span className="oc-definition-value">
                      {focusedEntity.notes || "No analyst notes recorded."}
                    </span>
                  </div>
                </div>
                <div className="oc-panel">
                  <div className="oc-card-header oc-card-header-compact">
                    <div>
                      <p className="oc-callout-title">Latest enrichment</p>
                      <p className="oc-callout-body">
                        {focusedRun
                          ? `Completed ${focusedRun.completed_at}`
                          : "No enrichment run stored yet."}
                      </p>
                    </div>
                    {focusedRun ? (
                      <span className={runBadgeClass(focusedRun.status)}>
                        {focusedRun.status}
                      </span>
                    ) : null}
                  </div>
                  {focusedRun ? (
                    <div className="oc-module-list">
                      {focusedRun.results.map((moduleResult) => (
                        <div className="oc-module-row" key={moduleResult.module_name}>
                          <div>
                            <strong>{formatModuleName(moduleResult.module_name)}</strong>
                            <p>{summarizeModuleResult(moduleResult)}</p>
                          </div>
                          <span className={moduleBadgeClass(moduleResult.status)}>
                            {moduleResult.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          ) : null}

          <div className="oc-divider" />

          <form className="oc-form" onSubmit={onSaveEntity}>
            <div className="oc-field-pair">
              <label className="oc-field">
                <span className="oc-label">Type</span>
                <select
                  className="oc-select"
                  value={entityDraft.type}
                  onChange={(event) =>
                    onEntityDraftChange({
                      ...entityDraft,
                      type: event.target.value as EntityType,
                    })
                  }
                >
                  <option value="domain">domain</option>
                  <option value="url">url</option>
                </select>
              </label>
              <label className="oc-field">
                <span className="oc-label">Confidence</span>
                <select
                  className="oc-select"
                  value={entityDraft.confidence}
                  onChange={(event) =>
                    onEntityDraftChange({
                      ...entityDraft,
                      confidence: event.target.value as Confidence,
                    })
                  }
                >
                  <option value="unknown">unknown</option>
                  <option value="low">low</option>
                  <option value="medium">medium</option>
                  <option value="high">high</option>
                </select>
              </label>
            </div>
            <label className="oc-field">
              <span className="oc-label">Value</span>
              <input
                className="oc-input oc-mono"
                required
                placeholder={entityDraft.type === "url" ? "https://example.com/" : "example.com"}
                value={entityDraft.value}
                onChange={(event) =>
                  onEntityDraftChange({ ...entityDraft, value: event.target.value })
                }
              />
            </label>
            <label className="oc-field">
              <span className="oc-label">Display name</span>
              <input
                className="oc-input"
                value={entityDraft.displayName}
                onChange={(event) =>
                  onEntityDraftChange({ ...entityDraft, displayName: event.target.value })
                }
              />
            </label>
            <label className="oc-field">
              <span className="oc-label">Description</span>
              <textarea
                className="oc-textarea"
                rows={2}
                value={entityDraft.description}
                onChange={(event) =>
                  onEntityDraftChange({ ...entityDraft, description: event.target.value })
                }
              />
            </label>
            <label className="oc-field">
              <span className="oc-label">Notes</span>
              <textarea
                className="oc-textarea"
                rows={3}
                value={entityDraft.notes}
                onChange={(event) =>
                  onEntityDraftChange({ ...entityDraft, notes: event.target.value })
                }
              />
            </label>
            <label className="oc-field">
              <span className="oc-label">Tags</span>
              <input
                className="oc-input"
                value={entityDraft.tags}
                onChange={(event) =>
                  onEntityDraftChange({ ...entityDraft, tags: event.target.value })
                }
              />
            </label>
            <div className="oc-form-footer">
              <button className="oc-btn oc-btn-primary" type="submit">
                {editingEntityId ? "Save entity" : "Add entity"}
              </button>
              {editingEntityId ? (
                <button className="oc-btn" onClick={onCancelEdit} type="button">
                  Cancel
                </button>
              ) : null}
            </div>
          </form>

          <div className="oc-entity-list">
            {entityLoading ? <p className="oc-empty-state">Loading entities.</p> : null}
            {!entityLoading && entities.length === 0 ? (
              <p className="oc-empty-state">Add a domain or URL to start this case.</p>
            ) : null}
            {entities.map((entity) => (
              <article className="oc-panel oc-entity-row" key={entity.id}>
                <div>
                  <div className="oc-entity-title">
                    <strong>{entity.display_name}</strong>
                    <span className={confidenceBadgeClass(entity.confidence)}>
                      {entity.confidence} confidence
                    </span>
                    {latestRunByEntity.get(entity.id) ? (
                      <span className={runBadgeClass(latestRunByEntity.get(entity.id)!.status)}>
                        {latestRunByEntity.get(entity.id)!.status} enrichment
                      </span>
                    ) : null}
                  </div>
                  <code className="oc-mono oc-technical">{entity.value}</code>
                  {latestRunByEntity.get(entity.id) ? (
                    <p>
                      Latest enrichment: {latestRunByEntity.get(entity.id)!.results.length} passive
                      modules at {latestRunByEntity.get(entity.id)!.completed_at}
                    </p>
                  ) : null}
                  {entity.notes ? <p>{entity.notes}</p> : null}
                  {entity.tags.length > 0 ? (
                    <div className="oc-tag-row">
                      {entity.tags.map((tag) => (
                        <span className="oc-badge oc-badge-muted" key={tag}>
                          {tag}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
                <div className="oc-row-actions">
                  <button
                    className="oc-btn oc-btn-primary oc-btn-sm"
                    disabled={enrichmentLoadingId === entity.id}
                    onClick={() => onRunEnrichment(entity)}
                    type="button"
                  >
                    {enrichmentLoadingId === entity.id ? "Running" : "Enrich"}
                  </button>
                  <button
                    className="oc-btn oc-btn-sm"
                    onClick={() => onEditEntity(entity)}
                    type="button"
                  >
                    Edit
                  </button>
                  <button
                    className="oc-btn oc-btn-danger oc-btn-sm"
                    onClick={() => onDeleteEntity(entity)}
                    type="button"
                  >
                    Delete
                  </button>
                </div>
              </article>
            ))}
          </div>
        </>
      ) : (
        <p className="oc-empty-state">Select or create a scoped case before adding entities.</p>
      )}
    </section>
  );
}

export function createEmptyEntityDraft() {
  return emptyEntity;
}
