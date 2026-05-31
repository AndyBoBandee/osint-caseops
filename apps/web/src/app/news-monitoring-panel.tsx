import { FormEvent } from "react";

import {
  CaseSummary,
  EvidenceLinkRecord,
  KeywordSetFormState,
  NewsIngestionRunRecord,
  NewsKeywordSet,
  NewsResultRecord,
  NewsReviewStatus,
  TrendSummary,
} from "./case-types";

type NewsMonitoringPanelProps = {
  evidenceLinks: EvidenceLinkRecord[];
  draftScanLoading: boolean;
  keywordDraft: KeywordSetFormState;
  keywordSets: NewsKeywordSet[];
  newsLoading: boolean;
  newsResults: NewsResultRecord[];
  newsRuns: NewsIngestionRunRecord[];
  scanLoadingId: string | null;
  selectedCase: CaseSummary | null;
  trendSummary: TrendSummary | null;
  onKeywordDraftChange: (draft: KeywordSetFormState) => void;
  onCreateKeywordSet: (event: FormEvent<HTMLFormElement>) => void;
  onRunDraftScan: () => void;
  onRunKeywordSet: (keywordSet: NewsKeywordSet) => void;
  onSaveEvidence: (result: NewsResultRecord) => void;
  onUpdateReviewStatus: (result: NewsResultRecord, reviewStatus: NewsReviewStatus) => void;
};

function statusBadgeClass(status: NewsIngestionRunRecord["status"]) {
  if (status === "success") {
    return "oc-badge oc-badge-success";
  }

  if (status === "partial") {
    return "oc-badge oc-badge-medium";
  }

  return "oc-badge oc-badge-danger";
}

function reviewBadgeClass(status: NewsReviewStatus) {
  if (status === "relevant") {
    return "oc-badge oc-badge-success";
  }

  if (status === "not_relevant") {
    return "oc-badge oc-badge-muted";
  }

  return "oc-badge oc-badge-info";
}

function trendTypeLabel(value: string) {
  return value.replaceAll("_", " ");
}

function visibleTrendGroups(trendSummary: TrendSummary | null): TrendSummary["groups"] {
  if (!trendSummary) {
    return [];
  }

  const selected = new Map<string, TrendSummary["groups"][number]>();
  const requiredTypes: TrendSummary["groups"][number]["group_type"][] = [
    "keyword",
    "source",
    "time_window",
    "theme",
  ];

  for (const groupType of requiredTypes) {
    const group = trendSummary.groups.find((candidate) => candidate.group_type === groupType);
    if (group) {
      selected.set(`${group.group_type}:${group.label}`, group);
    }
  }

  for (const group of trendSummary.groups) {
    if (selected.size >= 8) {
      break;
    }
    selected.set(`${group.group_type}:${group.label}`, group);
  }

  return Array.from(selected.values());
}

export function NewsMonitoringPanel({
  evidenceLinks,
  draftScanLoading,
  keywordDraft,
  keywordSets,
  newsLoading,
  newsResults,
  newsRuns,
  scanLoadingId,
  selectedCase,
  trendSummary,
  onKeywordDraftChange,
  onCreateKeywordSet,
  onRunDraftScan,
  onRunKeywordSet,
  onSaveEvidence,
  onUpdateReviewStatus,
}: NewsMonitoringPanelProps) {
  const latestRun = newsRuns[0] ?? null;
  const displayedTrendGroups = visibleTrendGroups(trendSummary);

  return (
    <section className="oc-card oc-news-monitor" id="news-monitoring" aria-label="Public news monitoring">
      <div className="oc-card-header">
        <div>
          <h2 className="oc-card-title">Public news monitoring</h2>
          <p className="oc-card-description">
            {selectedCase
              ? "Scoped keyword scans, review queue, trend groups, and evidence links."
              : "Select a scoped case to monitor public news and search results."}
          </p>
        </div>
        {latestRun ? <span className={statusBadgeClass(latestRun.status)}>{latestRun.status}</span> : null}
      </div>

      {selectedCase ? (
        <div className="oc-news-grid">
          <div className="oc-panel">
            <form className="oc-form" onSubmit={onCreateKeywordSet}>
              <h3 className="oc-callout-title">Keyword set</h3>
              <label className="oc-field">
                <span className="oc-label">Name</span>
                <input
                  className="oc-input"
                  required
                  value={keywordDraft.name}
                  onChange={(event) =>
                    onKeywordDraftChange({ ...keywordDraft, name: event.target.value })
                  }
                />
              </label>
              <label className="oc-field">
                <span className="oc-label">Keywords</span>
                <textarea
                  className="oc-textarea"
                  required
                  rows={3}
                  value={keywordDraft.keywords}
                  onChange={(event) =>
                    onKeywordDraftChange({ ...keywordDraft, keywords: event.target.value })
                  }
                />
              </label>
              <label className="oc-field">
                <span className="oc-label">Scope notes</span>
                <textarea
                  className="oc-textarea"
                  rows={2}
                  value={keywordDraft.scopeNotes}
                  onChange={(event) =>
                    onKeywordDraftChange({ ...keywordDraft, scopeNotes: event.target.value })
                  }
                />
              </label>
              <div className="oc-form-footer">
                <button
                  className="oc-btn oc-btn-primary"
                  disabled={scanLoadingId !== null}
                  onClick={onRunDraftScan}
                  type="button"
                >
                  {draftScanLoading ? "Scanning" : "Run scoped scan"}
                </button>
                <button className="oc-btn" type="submit">
                  Save keyword set
                </button>
              </div>
            </form>

            <div className="oc-divider" />

            <div className="oc-module-list">
              {keywordSets.length === 0 ? (
                <p className="oc-empty-state">Create a keyword set to run a public scan.</p>
              ) : null}
              {keywordSets.map((keywordSet) => (
                <div className="oc-module-row" key={keywordSet.id}>
                  <div>
                    <strong>{keywordSet.name}</strong>
                    <p>{keywordSet.keywords.join(", ")}</p>
                  </div>
                  <button
                    className="oc-btn oc-btn-primary oc-btn-sm"
                    disabled={scanLoadingId !== null}
                    onClick={() => onRunKeywordSet(keywordSet)}
                    type="button"
                  >
                    {scanLoadingId === keywordSet.id ? "Scanning" : "Scan"}
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="oc-panel">
            <div className="oc-card-header oc-card-header-compact">
              <div>
                <p className="oc-callout-title">Review queue</p>
                <p className="oc-callout-body">
                  {newsLoading ? "Loading public results." : `${newsResults.length} stored result(s)`}
                </p>
              </div>
              <span className="oc-badge oc-badge-info">{evidenceLinks.length} evidence links</span>
            </div>
            {latestRun?.error_message ? (
              <div className="oc-callout oc-callout-warning oc-notice">
                <p className="oc-callout-body">{latestRun.error_message}</p>
              </div>
            ) : null}
            <div className="oc-news-result-list">
              {newsResults.length === 0 ? (
                <p className="oc-empty-state">No public news results have been stored yet.</p>
              ) : null}
              {newsResults.map((result) => (
                <article className="oc-panel oc-news-result" key={result.id}>
                  <div className="oc-news-result-header">
                    <div>
                      <span className="oc-badge oc-badge-muted">{result.keyword}</span>
                      <h3>{result.title || result.source_url}</h3>
                    </div>
                    <span className={reviewBadgeClass(result.review_status)}>
                      {result.review_status.replace("_", " ")}
                    </span>
                  </div>
                  <p>{result.snippet || "No snippet returned by the public provider."}</p>
                  <div className="oc-case-meta">
                    <span>{result.publisher || "Unknown publisher"}</span>
                    {result.published_at ? <span>Published {result.published_at}</span> : null}
                    <span>Retrieved {result.retrieved_at}</span>
                    <span>{result.recency_cue}</span>
                    <span>{result.source_quality.replace("_", " ")}</span>
                  </div>
                  <p className="oc-empty-state">{result.prioritization_cue}</p>
                  <a className="oc-technical" href={result.source_url} rel="noreferrer" target="_blank">
                    {result.source_url}
                  </a>
                  <div className="oc-row-actions">
                    {(["pending", "relevant", "not_relevant"] as NewsReviewStatus[]).map(
                      (reviewStatus) => (
                        <button
                          className="oc-btn oc-btn-sm"
                          disabled={result.review_status === reviewStatus}
                          key={reviewStatus}
                          onClick={() => onUpdateReviewStatus(result, reviewStatus)}
                          type="button"
                        >
                          {reviewStatus.replace("_", " ")}
                        </button>
                      ),
                    )}
                    <button
                      className="oc-btn oc-btn-primary oc-btn-sm"
                      disabled={result.saved_as_evidence}
                      onClick={() => onSaveEvidence(result)}
                      type="button"
                    >
                      {result.saved_as_evidence ? "Saved" : "Save evidence"}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </div>

          <div className="oc-panel">
            <div className="oc-card-header oc-card-header-compact">
              <div>
                <p className="oc-callout-title">Trend summary</p>
                <p className="oc-callout-body">
                  {trendSummary ? `Generated ${trendSummary.generated_at}` : "No trend groups yet."}
                </p>
              </div>
            </div>
            <div className="oc-module-list">
              {trendSummary?.groups.length ? null : (
                <p className="oc-empty-state">Run a scan to group results by keyword, source, time, and theme.</p>
              )}
              {displayedTrendGroups.map((group) => (
                <div className="oc-module-row" key={`${group.group_type}:${group.label}`}>
                  <div>
                    <strong>
                      {trendTypeLabel(group.group_type)}: {group.label}
                    </strong>
                    <p>{group.priority_cue}</p>
                    <p>{group.confidence_language}</p>
                  </div>
                  <span className="oc-badge oc-badge-info">{group.result_count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <p className="oc-empty-state">Select or create a case before running public news scans.</p>
      )}
    </section>
  );
}
