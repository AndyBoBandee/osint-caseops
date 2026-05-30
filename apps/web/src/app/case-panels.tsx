import { FormEvent } from "react";

import { CaseFormState, CaseStatus, CaseSummary } from "./case-types";

type CaseRailProps = {
  cases: CaseSummary[];
  selectedCaseId: string;
  createDraft: CaseFormState;
  onCreateDraftChange: (draft: CaseFormState) => void;
  onCreateCase: (event: FormEvent<HTMLFormElement>) => void;
  onSelectCase: (caseRecord: CaseSummary) => void;
};

type CaseDetailProps = {
  caseDraft: CaseFormState | null;
  error: string;
  notice: string;
  selectedCase: CaseSummary | null;
  onCaseDraftChange: (draft: CaseFormState) => void;
  onDeleteCase: () => void;
  onUpdateCase: (event: FormEvent<HTMLFormElement>) => void;
};

function statusBadgeClass(status: CaseStatus) {
  if (status === "active") {
    return "oc-badge oc-badge-success";
  }

  if (status === "closed") {
    return "oc-badge oc-badge-danger";
  }

  return "oc-badge oc-badge-muted";
}

export function CaseRail({
  cases,
  selectedCaseId,
  createDraft,
  onCreateDraftChange,
  onCreateCase,
  onSelectCase,
}: CaseRailProps) {
  return (
    <section className="oc-card" id="dashboard" aria-label="Cases">
      <div className="oc-card-header">
        <div>
          <h2 className="oc-card-title">Cases</h2>
          <p className="oc-card-description">
            {cases.length} scoped case{cases.length === 1 ? "" : "s"}
          </p>
        </div>
      </div>

      {cases.length > 0 ? (
        <div className="oc-case-list">
          {cases.map((caseRecord) => (
            <button
              className={
                caseRecord.id === selectedCaseId
                  ? "oc-panel oc-case-row is-active"
                  : "oc-panel oc-case-row"
              }
              key={caseRecord.id}
              onClick={() => onSelectCase(caseRecord)}
              type="button"
            >
              <span>
                <strong>{caseRecord.title}</strong>
                <small>{caseRecord.scope_category}</small>
              </span>
              <span className="oc-badge oc-badge-info">{caseRecord.entity_count} entities</span>
            </button>
          ))}
        </div>
      ) : (
        <p className="oc-empty-state">
          Create your first case to begin organizing public-source research.
        </p>
      )}

      <div className="oc-divider" />

      <form className="oc-form" onSubmit={onCreateCase}>
        <h3 className="oc-card-title">Create case</h3>
        <label className="oc-field">
          <span className="oc-label">Title</span>
          <input
            className="oc-input"
            required
            value={createDraft.title}
            onChange={(event) =>
              onCreateDraftChange({ ...createDraft, title: event.target.value })
            }
          />
        </label>
        <label className="oc-field">
          <span className="oc-label">Objective</span>
          <textarea
            className="oc-textarea"
            required
            rows={3}
            value={createDraft.objective}
            onChange={(event) =>
              onCreateDraftChange({ ...createDraft, objective: event.target.value })
            }
          />
        </label>
        <div className="oc-field-pair">
          <label className="oc-field">
            <span className="oc-label">Scope</span>
            <select
              className="oc-select"
              value={createDraft.scopeCategory}
              onChange={(event) =>
                onCreateDraftChange({ ...createDraft, scopeCategory: event.target.value })
              }
            >
              <option>Vendor review</option>
              <option>Business exposure review</option>
              <option>Scam review</option>
              <option>Owned asset review</option>
            </select>
          </label>
          <label className="oc-field">
            <span className="oc-label">Type</span>
            <select
              className="oc-select"
              value={createDraft.caseType}
              onChange={(event) =>
                onCreateDraftChange({ ...createDraft, caseType: event.target.value })
              }
            >
              <option>Vendor risk snapshot</option>
              <option>Domain review</option>
              <option>Suspicious URL review</option>
              <option>Owned asset exposure check</option>
            </select>
          </label>
        </div>
        <label className="oc-field">
          <span className="oc-label">Scope notes</span>
          <textarea
            className="oc-textarea"
            rows={2}
            value={createDraft.scopeNotes}
            onChange={(event) =>
              onCreateDraftChange({ ...createDraft, scopeNotes: event.target.value })
            }
          />
        </label>
        <label className="oc-field">
          <span className="oc-label">Tags</span>
          <input
            className="oc-input"
            placeholder="vendor, review"
            value={createDraft.tags}
            onChange={(event) =>
              onCreateDraftChange({ ...createDraft, tags: event.target.value })
            }
          />
        </label>
        <label className="oc-check-row">
          <input
            required
            checked={createDraft.scopeAcknowledged}
            onChange={(event) =>
              onCreateDraftChange({
                ...createDraft,
                scopeAcknowledged: event.target.checked,
              })
            }
            type="checkbox"
          />
          I confirm this case is lawful, ethical, public-source, and scoped.
        </label>
        <button className="oc-btn oc-btn-primary" type="submit">
          Create case
        </button>
      </form>
    </section>
  );
}

export function CaseDetailPanel({
  caseDraft,
  error,
  notice,
  selectedCase,
  onCaseDraftChange,
  onDeleteCase,
  onUpdateCase,
}: CaseDetailProps) {
  return (
    <section className="oc-card" id="case-detail" aria-label="Case detail">
      <div className="oc-card-header">
        <div>
          <h2 className="oc-card-title">Case detail</h2>
          <p className="oc-card-description">
            {selectedCase ? selectedCase.case_type : "No case selected"}
          </p>
        </div>
        {selectedCase ? (
          <span className={statusBadgeClass(selectedCase.status)}>{selectedCase.status}</span>
        ) : null}
      </div>

      {selectedCase ? (
        <div className="oc-tabs" role="tablist" aria-label="Case sections">
          {["Summary", "Entities", "Findings", "Evidence", "Relationships", "Timeline", "Notes"].map(
            (tab, index) => (
              <button
                aria-selected={index === 0}
                className={index === 0 ? "oc-tab is-active" : "oc-tab"}
                key={tab}
                role="tab"
                type="button"
              >
                {tab}
              </button>
            ),
          )}
        </div>
      ) : null}

      <div className="oc-divider" />

      {notice ? <div className="oc-callout oc-callout-success oc-notice">{notice}</div> : null}
      {error ? <div className="oc-callout oc-callout-warning oc-notice">{error}</div> : null}

      {selectedCase && caseDraft ? (
        <form className="oc-form" onSubmit={onUpdateCase}>
          <div className="oc-case-meta">
            <span>Created {selectedCase.created_at}</span>
            <span>Updated {selectedCase.updated_at}</span>
            <span>{selectedCase.entity_count} entities tracked</span>
          </div>
          <label className="oc-field">
            <span className="oc-label">Title</span>
            <input
              className="oc-input"
              required
              value={caseDraft.title}
              onChange={(event) =>
                onCaseDraftChange({ ...caseDraft, title: event.target.value })
              }
            />
          </label>
          <label className="oc-field">
            <span className="oc-label">Objective</span>
            <textarea
              className="oc-textarea"
              required
              rows={3}
              value={caseDraft.objective}
              onChange={(event) =>
                onCaseDraftChange({ ...caseDraft, objective: event.target.value })
              }
            />
          </label>
          <div className="oc-field-pair">
            <label className="oc-field">
              <span className="oc-label">Scope</span>
              <input
                className="oc-input"
                required
                value={caseDraft.scopeCategory}
                onChange={(event) =>
                  onCaseDraftChange({ ...caseDraft, scopeCategory: event.target.value })
                }
              />
            </label>
            <label className="oc-field">
              <span className="oc-label">Status</span>
              <select
                className="oc-select"
                value={caseDraft.status}
                onChange={(event) =>
                  onCaseDraftChange({
                    ...caseDraft,
                    status: event.target.value as CaseStatus,
                  })
                }
              >
                <option value="active">active</option>
                <option value="archived">archived</option>
                <option value="closed">closed</option>
              </select>
            </label>
          </div>
          <label className="oc-field">
            <span className="oc-label">Scope notes</span>
            <textarea
              className="oc-textarea"
              rows={3}
              value={caseDraft.scopeNotes}
              onChange={(event) =>
                onCaseDraftChange({ ...caseDraft, scopeNotes: event.target.value })
              }
            />
          </label>
          <label className="oc-field">
            <span className="oc-label">Analyst notes</span>
            <textarea
              className="oc-textarea"
              rows={4}
              value={caseDraft.analystNotes}
              onChange={(event) =>
                onCaseDraftChange({ ...caseDraft, analystNotes: event.target.value })
              }
            />
          </label>
          <label className="oc-field">
            <span className="oc-label">Tags</span>
            <input
              className="oc-input"
              value={caseDraft.tags}
              onChange={(event) =>
                onCaseDraftChange({ ...caseDraft, tags: event.target.value })
              }
            />
          </label>
          <div className="oc-form-footer">
            <button className="oc-btn oc-btn-primary" type="submit">
              Save case
            </button>
            <button className="oc-btn oc-btn-danger" onClick={onDeleteCase} type="button">
              Delete case
            </button>
          </div>
          <div className="oc-callout">
            <div>
              <p className="oc-callout-title">Scope acknowledged</p>
              <p className="oc-callout-body">{selectedCase.scope_acknowledged_at}</p>
            </div>
          </div>
        </form>
      ) : (
        <p className="oc-empty-state">
          Create your first case to begin organizing public-source research.
        </p>
      )}
    </section>
  );
}
