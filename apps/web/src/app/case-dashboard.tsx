"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { apiRequest } from "./case-api";
import { CaseDetailPanel, CaseRail } from "./case-panels";
import {
  CaseFormState,
  CaseSummary,
  Confidence,
  draftFromCase,
  draftFromEntity,
  emptyCreateCase,
  emptyEntity,
  EnrichmentRunRecord,
  EntityFormState,
  EntityRecord,
  tagsFromInput,
} from "./case-types";
import { EntityPanel } from "./entity-panel";

type CaseDashboardProps = {
  initialCases: CaseSummary[];
  initialApiOnline: boolean;
};

const confidenceOrder: Confidence[] = ["high", "medium", "low", "unknown"];

function confidenceBadgeClass(confidence: Confidence) {
  if (confidence === "high") {
    return "oc-badge oc-badge-high";
  }

  if (confidence === "medium") {
    return "oc-badge oc-badge-medium";
  }

  return "oc-badge oc-badge-low";
}

export function CaseDashboard({ initialCases, initialApiOnline }: CaseDashboardProps) {
  const [cases, setCases] = useState<CaseSummary[]>(initialCases);
  const [selectedCaseId, setSelectedCaseId] = useState(initialCases[0]?.id ?? "");
  const [createDraft, setCreateDraft] = useState<CaseFormState>(emptyCreateCase);
  const [caseDraft, setCaseDraft] = useState<CaseFormState | null>(
    initialCases[0] ? draftFromCase(initialCases[0]) : null,
  );
  const [entities, setEntities] = useState<EntityRecord[]>([]);
  const [enrichmentRuns, setEnrichmentRuns] = useState<EnrichmentRunRecord[]>([]);
  const [entityDraft, setEntityDraft] = useState<EntityFormState>(emptyEntity);
  const [editingEntityId, setEditingEntityId] = useState<string | null>(null);
  const [entityLoading, setEntityLoading] = useState(false);
  const [enrichmentLoadingId, setEnrichmentLoadingId] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState(initialApiOnline ? "" : "Start the API to manage cases.");

  const selectedCase = useMemo(
    () => cases.find((caseRecord) => caseRecord.id === selectedCaseId) ?? null,
    [cases, selectedCaseId],
  );

  useEffect(() => {
    let ignore = false;

    async function loadEntities() {
      if (!selectedCaseId) {
        setEntities([]);
        setEnrichmentRuns([]);
        return;
      }

      setEntityLoading(true);
      setError("");

      try {
        const [nextEntities, nextEnrichmentRuns] = await Promise.all([
          apiRequest<EntityRecord[]>(`/cases/${selectedCaseId}/entities`),
          apiRequest<EnrichmentRunRecord[]>(`/cases/${selectedCaseId}/enrichment-runs`),
        ]);
        if (!ignore) {
          setEntities(nextEntities);
          setEnrichmentRuns(nextEnrichmentRuns);
        }
      } catch (caught) {
        if (!ignore) {
          setError(caught instanceof Error ? caught.message : "Could not load entities.");
        }
      } finally {
        if (!ignore) {
          setEntityLoading(false);
        }
      }
    }

    void loadEntities();

    return () => {
      ignore = true;
    };
  }, [selectedCaseId]);

  async function handleCreateCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");

    try {
      const created = await apiRequest<CaseSummary>("/cases", {
        method: "POST",
        body: JSON.stringify({
          title: createDraft.title,
          objective: createDraft.objective,
          scope_category: createDraft.scopeCategory,
          scope_notes: createDraft.scopeNotes,
          case_type: createDraft.caseType,
          status: createDraft.status,
          scope_acknowledged: createDraft.scopeAcknowledged,
          tags: tagsFromInput(createDraft.tags),
          analyst_notes: createDraft.analystNotes,
        }),
      });

      setCases((currentCases) => [created, ...currentCases]);
      setSelectedCaseId(created.id);
      setCaseDraft(draftFromCase(created));
      setCreateDraft(emptyCreateCase);
      setNotice("Case created.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create case.");
    }
  }

  async function handleUpdateCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCase || !caseDraft) {
      return;
    }

    setError("");
    setNotice("");

    try {
      const updated = await apiRequest<CaseSummary>(`/cases/${selectedCase.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: caseDraft.title,
          objective: caseDraft.objective,
          scope_category: caseDraft.scopeCategory,
          scope_notes: caseDraft.scopeNotes,
          case_type: caseDraft.caseType,
          status: caseDraft.status,
          tags: tagsFromInput(caseDraft.tags),
          analyst_notes: caseDraft.analystNotes,
        }),
      });

      setCases((currentCases) =>
        currentCases.map((caseRecord) => (caseRecord.id === updated.id ? updated : caseRecord)),
      );
      setCaseDraft(draftFromCase(updated));
      setNotice("Case saved.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save case.");
    }
  }

  async function handleDeleteCase() {
    if (!selectedCase || !window.confirm(`Delete case "${selectedCase.title}"?`)) {
      return;
    }

    setError("");
    setNotice("");

    try {
      await apiRequest<void>(`/cases/${selectedCase.id}`, { method: "DELETE" });
      const remaining = cases.filter((caseRecord) => caseRecord.id !== selectedCase.id);
      const nextSelected = remaining[0] ?? null;

      setCases(remaining);
      setSelectedCaseId(nextSelected?.id ?? "");
      setCaseDraft(nextSelected ? draftFromCase(nextSelected) : null);
      setEntities([]);
      setEnrichmentRuns([]);
      setNotice("Case deleted.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not delete case.");
    }
  }

  async function handleSaveEntity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCase) {
      return;
    }

    setError("");
    setNotice("");

    try {
      const saved = await apiRequest<EntityRecord>(
        editingEntityId
          ? `/entities/${editingEntityId}`
          : `/cases/${selectedCase.id}/entities`,
        {
          method: editingEntityId ? "PATCH" : "POST",
          body: JSON.stringify({
            type: entityDraft.type,
            value: entityDraft.value,
            display_name: entityDraft.displayName,
            description: entityDraft.description,
            confidence: entityDraft.confidence,
            tags: tagsFromInput(entityDraft.tags),
            notes: entityDraft.notes,
          }),
        },
      );

      setEntities((currentEntities) => {
        if (editingEntityId) {
          return currentEntities.map((entity) => (entity.id === saved.id ? saved : entity));
        }
        return [saved, ...currentEntities];
      });
      setCases((currentCases) =>
        currentCases.map((caseRecord) =>
          caseRecord.id === selectedCase.id
            ? {
                ...caseRecord,
                entity_count: editingEntityId
                  ? caseRecord.entity_count
                  : caseRecord.entity_count + 1,
                updated_at: saved.updated_at,
              }
            : caseRecord,
        ),
      );
      setEntityDraft(emptyEntity);
      setEditingEntityId(null);
      setNotice(editingEntityId ? "Entity saved." : "Entity added.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save entity.");
    }
  }

  async function handleDeleteEntity(entity: EntityRecord) {
    if (!window.confirm(`Delete entity "${entity.display_name}"?`)) {
      return;
    }

    setError("");
    setNotice("");

    try {
      await apiRequest<void>(`/entities/${entity.id}`, { method: "DELETE" });
      setEntities((currentEntities) =>
        currentEntities.filter((currentEntity) => currentEntity.id !== entity.id),
      );
      setEnrichmentRuns((currentRuns) =>
        currentRuns.filter((run) => run.entity_id !== entity.id),
      );
      setCases((currentCases) =>
        currentCases.map((caseRecord) =>
          caseRecord.id === entity.case_id
            ? {
                ...caseRecord,
                entity_count: Math.max(0, caseRecord.entity_count - 1),
              }
            : caseRecord,
        ),
      );
      if (editingEntityId === entity.id) {
        setEditingEntityId(null);
        setEntityDraft(emptyEntity);
      }
      setNotice("Entity deleted.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not delete entity.");
    }
  }

  async function handleRunEnrichment(entity: EntityRecord) {
    setError("");
    setNotice("");
    setEnrichmentLoadingId(entity.id);

    try {
      const run = await apiRequest<EnrichmentRunRecord>(
        `/entities/${entity.id}/enrichment-runs`,
        { method: "POST" },
      );

      setEnrichmentRuns((currentRuns) => [
        run,
        ...currentRuns.filter((currentRun) => currentRun.id !== run.id),
      ]);
      setCases((currentCases) =>
        currentCases.map((caseRecord) =>
          caseRecord.id === entity.case_id
            ? {
                ...caseRecord,
                updated_at: run.created_at,
              }
            : caseRecord,
        ),
      );
      setNotice(
        run.status === "success"
          ? "Enrichment completed."
          : `Enrichment completed with ${run.status} status.`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not run enrichment.");
    } finally {
      setEnrichmentLoadingId(null);
    }
  }

  function selectCase(caseRecord: CaseSummary) {
    setSelectedCaseId(caseRecord.id);
    setCaseDraft(draftFromCase(caseRecord));
    setEditingEntityId(null);
    setEntityDraft(emptyEntity);
  }

  return (
    <div className="oc-dashboard">
      <OperationsOverview
        cases={cases}
        enrichmentRuns={enrichmentRuns}
        entities={entities}
        selectedCase={selectedCase}
      />

      <div className="oc-workspace-grid">
        <CaseRail
          cases={cases}
          selectedCaseId={selectedCaseId}
          createDraft={createDraft}
          onCreateDraftChange={setCreateDraft}
          onCreateCase={handleCreateCase}
          onSelectCase={selectCase}
        />
        <CaseDetailPanel
          caseDraft={caseDraft}
          error={error}
          notice={notice}
          selectedCase={selectedCase}
          onCaseDraftChange={setCaseDraft}
          onDeleteCase={handleDeleteCase}
          onUpdateCase={handleUpdateCase}
        />
        <EntityPanel
          editingEntityId={editingEntityId}
          enrichmentLoadingId={enrichmentLoadingId}
          enrichmentRuns={enrichmentRuns}
          entities={entities}
          entityDraft={entityDraft}
          entityLoading={entityLoading}
          selectedCase={selectedCase}
          onCancelEdit={() => {
            setEditingEntityId(null);
            setEntityDraft(emptyEntity);
          }}
          onDeleteEntity={(entity) => void handleDeleteEntity(entity)}
          onEditEntity={(entity) => {
            setEditingEntityId(entity.id);
            setEntityDraft(draftFromEntity(entity));
          }}
          onEntityDraftChange={setEntityDraft}
          onRunEnrichment={(entity) => void handleRunEnrichment(entity)}
          onSaveEntity={handleSaveEntity}
        />
      </div>

      <InvestigationScreens
        enrichmentRuns={enrichmentRuns}
        entities={entities}
        selectedCase={selectedCase}
      />
    </div>
  );
}

function OperationsOverview({
  cases,
  enrichmentRuns,
  entities,
  selectedCase,
}: {
  cases: CaseSummary[];
  enrichmentRuns: EnrichmentRunRecord[];
  entities: EntityRecord[];
  selectedCase: CaseSummary | null;
}) {
  const activeCases = cases.filter((caseRecord) => caseRecord.status === "active").length;
  const totalEntities = cases.reduce((sum, caseRecord) => sum + caseRecord.entity_count, 0);
  const confidenceCounts = confidenceOrder.map((confidence) => ({
    confidence,
    count: entities.filter((entity) => entity.confidence === confidence).length,
  }));

  return (
    <section className="oc-grid oc-grid-4" aria-label="Dashboard cards">
      <article className="oc-card oc-stat-card">
        <span className="oc-stat-label">Active cases</span>
        <div className="oc-stat-value">{activeCases}</div>
        <div className="oc-stat-trend">Scope-first investigations</div>
      </article>
      <article className="oc-card oc-stat-card">
        <span className="oc-stat-label">Entities tracked</span>
        <div className="oc-stat-value">{totalEntities}</div>
        <div className="oc-stat-trend">Domains and URLs</div>
      </article>
      <article className="oc-card oc-stat-card">
        <span className="oc-stat-label">Enrichment runs</span>
        <div className="oc-stat-value">{enrichmentRuns.length}</div>
        <div className="oc-stat-trend">Stored passive checks</div>
      </article>
      <article className="oc-card oc-stat-card">
        <span className="oc-stat-label">Recent alerts</span>
        <div className="oc-stat-value">{selectedCase ? 1 : 0}</div>
        <div className="oc-stat-trend is-negative">Review confidence before reporting</div>
      </article>
      <article className="oc-card">
        <div className="oc-card-header">
          <div>
            <h2 className="oc-card-title">Findings by confidence</h2>
            <p className="oc-card-description">Color and text indicate confidence.</p>
          </div>
        </div>
        <div className="oc-summary-strip">
          {confidenceCounts.map(({ confidence, count }) => (
            <span className={confidenceBadgeClass(confidence)} key={confidence}>
              {confidence}: {count}
            </span>
          ))}
        </div>
      </article>
      <article className="oc-card">
        <div className="oc-card-header">
          <div>
            <h2 className="oc-card-title">Timeline activity</h2>
            <p className="oc-card-description">Recent workspace events.</p>
          </div>
        </div>
        <div className="oc-timeline">
          <div className="oc-timeline-item">
            <h3 className="oc-timeline-title">
              {selectedCase ? selectedCase.title : "No active case selected"}
            </h3>
            <div className="oc-timeline-meta">
              {selectedCase ? `Updated ${selectedCase.updated_at}` : "Create or select a case"}
            </div>
          </div>
        </div>
      </article>
      <article className="oc-card">
        <div className="oc-card-header">
          <div>
            <h2 className="oc-card-title">Recent alerts</h2>
            <p className="oc-card-description">Evidence-based review prompts.</p>
          </div>
        </div>
        <div className="oc-callout oc-callout-warning">
          <div>
            <p className="oc-callout-title">Confidence check</p>
            <p className="oc-callout-body">
              Review supporting evidence before drawing a conclusion.
            </p>
          </div>
        </div>
      </article>
    </section>
  );
}

function InvestigationScreens({
  enrichmentRuns,
  entities,
  selectedCase,
}: {
  enrichmentRuns: EnrichmentRunRecord[];
  entities: EntityRecord[];
  selectedCase: CaseSummary | null;
}) {
  const primaryEntity = entities[0] ?? null;
  const sourceEntity = entities.find((entity) => entity.type === "url") ?? primaryEntity;
  const graphEntities = entities.slice(0, 4);

  return (
    <section className="oc-screen-grid" aria-label="Investigation screens">
      <article className="oc-card" id="evidence-viewer">
        <div className="oc-card-header">
          <div>
            <h2 className="oc-card-title">Evidence viewer</h2>
            <p className="oc-card-description">Capture preview, source metadata, and notes.</p>
          </div>
        </div>
        <div className="oc-evidence-layout">
          <div className="oc-evidence-frame">
            <div className="oc-evidence-document">
              <h3>{selectedCase ? selectedCase.title : "No evidence selected"}</h3>
              <div className="oc-evidence-line" />
              <div className="oc-evidence-line" />
              <div className="oc-evidence-line is-short" />
            </div>
          </div>
          <aside className="oc-evidence-sidebar">
            <div className="oc-panel">
              <p className="oc-callout-title">Source URL</p>
              <p className="oc-callout-body oc-mono oc-technical">
                {sourceEntity?.value ?? "Not captured yet"}
              </p>
            </div>
            <div className="oc-panel">
              <p className="oc-callout-title">Capture timestamp</p>
              <p className="oc-callout-body oc-mono">
                {selectedCase ? selectedCase.updated_at : "Pending"}
              </p>
            </div>
            <div className="oc-action-bar">
              <button className="oc-btn oc-btn-sm" type="button">
                Open source
              </button>
              <button className="oc-btn oc-btn-sm" type="button">
                Copy link
              </button>
              <button className="oc-btn oc-btn-primary oc-btn-sm" type="button">
                Export
              </button>
            </div>
          </aside>
        </div>
      </article>

      <article className="oc-card" id="relationship-graph">
        <div className="oc-card-header">
          <div>
            <h2 className="oc-card-title">Relationship graph</h2>
            <p className="oc-card-description">Case-to-entity relationship map.</p>
          </div>
        </div>
        <div className="oc-graph">
          <div className="oc-graph-grid" />
          <div
            className="oc-graph-edge"
            style={{ left: "32%", top: "42%", width: "28%", transform: "rotate(-18deg)" }}
          />
          <div
            className="oc-graph-edge"
            style={{ left: "38%", top: "53%", width: "25%", transform: "rotate(22deg)" }}
          />
          <div className="oc-graph-node is-primary" style={{ left: "8%", top: "42%" }}>
            <span className="oc-graph-node-dot" />
            {selectedCase ? selectedCase.title : "Case"}
          </div>
          {graphEntities.length > 0 ? (
            graphEntities.map((entity, index) => (
              <div
                className="oc-graph-node"
                key={entity.id}
                style={{
                  left: `${52 + (index % 2) * 20}%`,
                  top: `${24 + index * 15}%`,
                }}
              >
                <span className="oc-graph-node-dot" />
                <span className="oc-mono">{entity.display_name}</span>
              </div>
            ))
          ) : (
            <div className="oc-graph-node" style={{ left: "58%", top: "46%" }}>
              <span className="oc-graph-node-dot" />
              Add an entity
            </div>
          )}
        </div>
      </article>

      <article className="oc-card" id="report-preview">
        <div className="oc-card-header">
          <div>
            <h2 className="oc-card-title">Report preview</h2>
            <p className="oc-card-description">Document view for defensible findings.</p>
          </div>
        </div>
        <div className="oc-report-layout">
          <aside className="oc-report-sidebar">
            <nav className="oc-report-nav" aria-label="Report sections">
              {[
                "Executive summary",
                "Scope and objective",
                "Methodology",
                "Findings",
                "Evidence table",
                "Timeline",
                "Limitations",
              ].map((section, index) => (
                <a
                  className={index === 0 ? "oc-nav-link is-active" : "oc-nav-link"}
                  href="#report-preview"
                  key={section}
                >
                  {section}
                </a>
              ))}
            </nav>
          </aside>
          <section className="oc-report-page" aria-label="Report page preview">
            <h1>{selectedCase ? selectedCase.title : "Case report"}</h1>
            <p>
              {selectedCase
                ? selectedCase.objective
                : "Create a scoped case to start a report preview."}
            </p>
            <div className="oc-report-metric-row">
              <div className="oc-report-metric">
                <span className="oc-report-metric-value">{entities.length}</span>
                Entities
              </div>
              <div className="oc-report-metric">
                <span className="oc-report-metric-value">{selectedCase ? 1 : 0}</span>
                Findings
              </div>
              <div className="oc-report-metric">
                <span className="oc-report-metric-value">{enrichmentRuns.length}</span>
                Enrichments
              </div>
              <div className="oc-report-metric">
                <span className="oc-report-metric-value">M</span>
                Confidence
              </div>
            </div>
            <h2>Evidence table</h2>
            <div className="oc-table-wrap">
              <table className="oc-table">
                <thead>
                  <tr>
                    <th>Entity</th>
                    <th>Type</th>
                    <th>Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {(entities.length > 0 ? entities : [primaryEntity]).map((entity, index) => (
                    <tr key={entity?.id ?? "empty"}>
                      <td>{entity?.display_name ?? "No entity added"}</td>
                      <td>{entity?.type ?? "Pending"}</td>
                      <td>{entity?.confidence ?? (index === 0 ? "Unknown" : "")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <h2>Limitations</h2>
            <p>
              This preview is based on limited public data. Review supporting evidence before
              drawing a conclusion.
            </p>
          </section>
        </div>
      </article>
    </section>
  );
}

export type { CaseSummary } from "./case-types";
