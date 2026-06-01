"use client";

import { useMemo, useState } from "react";

import { apiRequest } from "./case-api";
import {
  EvidenceFilter,
  FraudMonitorDashboardData,
  FraudMonitorJob,
  NewsResultRecord,
  NewsReviewStatus,
  ProviderInfo,
  ResultSort,
  TrendGroup,
} from "./fraud-monitor-types";

type FraudMonitorDashboardProps = {
  initialDashboard: FraudMonitorDashboardData;
  initialApiOnline: boolean;
};

type SchedulePatch = {
  enabled?: boolean;
  interval_minutes?: number;
};

type ReviewFilter = "all" | NewsReviewStatus;
type ResultQuery = {
  search: string;
  review: ReviewFilter;
  provider: string;
  evidence: EvidenceFilter;
  sort: ResultSort;
  limit: number;
  offset: number;
};

function statusClass(status: string) {
  if (status === "success" || status === "ready" || status === "relevant") {
    return "oc-badge oc-badge-success";
  }
  if (
    status === "partial" ||
    status === "missing_config" ||
    status === "partial_success" ||
    status === "pending"
  ) {
    return "oc-badge oc-badge-medium";
  }
  if (status === "not_relevant") {
    return "oc-badge oc-badge-muted";
  }
  return "oc-badge oc-badge-danger";
}

function issueClass(severity: string) {
  if (severity === "error") {
    return "oc-badge oc-badge-danger";
  }
  if (severity === "warning") {
    return "oc-badge oc-badge-medium";
  }
  return "oc-badge oc-badge-info";
}

function compactDate(value: string) {
  if (!value) {
    return "Never";
  }
  return value.replace("T", " ").replace("Z", " UTC");
}

function providerLabel(provider: string) {
  if (provider === "gdelt") {
    return "GDELT";
  }
  if (provider === "google_news_rss") {
    return "Google News RSS";
  }
  if (provider === "hn_algolia") {
    return "HN Algolia";
  }
  if (provider === "fixture") {
    return "Fixture";
  }
  if (provider === "brave") {
    return "Brave";
  }
  return provider.replaceAll("_", " ");
}

function sourceSummary(sourceUrl: string): string {
  try {
    const parsed = new URL(sourceUrl);
    const path = parsed.pathname === "/" ? "" : parsed.pathname;
    return `${parsed.hostname}${path}`.slice(0, 96);
  } catch {
    return sourceUrl;
  }
}

function trendLabel(group: TrendGroup) {
  return `${group.group_type.replaceAll("_", " ")}: ${group.label}`;
}

function sortLabel(sort: ResultSort) {
  if (sort === "retrieved_asc") {
    return "Retrieved oldest";
  }
  if (sort === "published_desc") {
    return "Published newest";
  }
  if (sort === "published_asc") {
    return "Published oldest";
  }
  if (sort === "title_asc") {
    return "Title A-Z";
  }
  if (sort === "source_asc") {
    return "Source A-Z";
  }
  if (sort === "review_asc") {
    return "Review status";
  }
  return "Retrieved newest";
}

function artifactLabel(type: string) {
  if (type === "source_url") {
    return "Source URL";
  }
  if (type === "html_snapshot") {
    return "HTML snapshot";
  }
  if (type === "text_snapshot") {
    return "Text snapshot";
  }
  if (type === "screenshot") {
    return "Screenshot";
  }
  return type.replaceAll("_", " ");
}

function makeInitialQuery(dashboard: FraudMonitorDashboardData): ResultQuery {
  return {
    search: dashboard.result_page.search,
    review: dashboard.result_page.review_filter,
    provider: dashboard.result_page.provider_filter,
    evidence: dashboard.result_page.evidence_filter,
    sort: dashboard.result_page.sort,
    limit: dashboard.result_page.limit,
    offset: dashboard.result_page.offset,
  };
}

function dashboardPath(query: ResultQuery) {
  const params = new URLSearchParams();
  if (query.search.trim()) {
    params.set("search", query.search.trim());
  }
  if (query.review !== "all") {
    params.set("review", query.review);
  }
  if (query.provider !== "all") {
    params.set("provider", query.provider);
  }
  if (query.evidence !== "all") {
    params.set("evidence", query.evidence);
  }
  params.set("sort", query.sort);
  params.set("limit", String(query.limit));
  params.set("offset", String(query.offset));
  return `/fraud-monitor/dashboard?${params.toString()}`;
}

export function FraudMonitorDashboard({
  initialDashboard,
  initialApiOnline,
}: FraudMonitorDashboardProps) {
  const [dashboard, setDashboard] = useState(initialDashboard);
  const [resultQuery, setResultQuery] = useState<ResultQuery>(() => makeInitialQuery(initialDashboard));
  const [isRunning, setIsRunning] = useState(false);
  const [isRunningDetailed, setIsRunningDetailed] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isSavingSchedule, setIsSavingSchedule] = useState(false);
  const [exportingFormat, setExportingFormat] = useState<"markdown" | "json" | null>(null);
  const [apiOnline, setApiOnline] = useState(initialApiOnline);
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>(initialDashboard.result_page.review_filter);
  const [providerFilter, setProviderFilter] = useState(initialDashboard.result_page.provider_filter);
  const [evidenceFilter, setEvidenceFilter] = useState<EvidenceFilter>(
    initialDashboard.result_page.evidence_filter,
  );
  const [searchDraft, setSearchDraft] = useState(initialDashboard.result_page.search);
  const [resultSort, setResultSort] = useState<ResultSort>(initialDashboard.result_page.sort);
  const [resultLimit, setResultLimit] = useState(initialDashboard.result_page.limit);
  const [evidenceNotes, setEvidenceNotes] = useState<Record<string, string>>({});
  const [selectedResultIds, setSelectedResultIds] = useState<string[]>([]);
  const [bulkReviewStatus, setBulkReviewStatus] = useState<NewsReviewStatus>("relevant");
  const [intervalDraft, setIntervalDraft] = useState(
    String(initialDashboard.schedule.interval_minutes),
  );
  const [notice, setNotice] = useState("");
  const [error, setError] = useState(initialApiOnline ? "" : "Start the API to run fraud scans.");

  const visibleTrends = useMemo(
    () => dashboard.trend_summary.groups.slice(0, 6),
    [dashboard.trend_summary.groups],
  );
  const resultProviders = useMemo(() => {
    return Array.from(
      new Set([
        ...dashboard.providers.map((provider) => provider.name),
        ...dashboard.results.map((result) => result.provider).filter(Boolean),
      ]),
    ).sort();
  }, [dashboard.providers, dashboard.results]);
  const visibleResultIds = useMemo(() => dashboard.results.map((result) => result.id), [dashboard.results]);
  const selectedVisibleCount = selectedResultIds.filter((id) => visibleResultIds.includes(id)).length;
  const totalAvailableArtifacts = dashboard.results.reduce(
    (total, result) => total + result.available_artifact_count,
    0,
  );
  const showDetailedProvider = !dashboard.providers.some((provider) => provider.name === dashboard.detailed_provider.name);
  const runDisabled =
    isRunning ||
    isRunningDetailed ||
    dashboard.runtime.is_running ||
    dashboard.runtime.ready_provider_count === 0;
  const detailedDisabled =
    isRunning ||
    isRunningDetailed ||
    dashboard.runtime.is_running ||
    dashboard.detailed_provider.status !== "ready";

  async function refreshDashboard(nextQuery: ResultQuery = resultQuery) {
    const nextDashboard = await apiRequest<FraudMonitorDashboardData>(dashboardPath(nextQuery));
    setDashboard(nextDashboard);
    const syncedQuery = makeInitialQuery(nextDashboard);
    setResultQuery(syncedQuery);
    setSearchDraft(syncedQuery.search);
    setReviewFilter(syncedQuery.review);
    setProviderFilter(syncedQuery.provider);
    setEvidenceFilter(syncedQuery.evidence);
    setResultSort(syncedQuery.sort);
    setResultLimit(syncedQuery.limit);
    setIntervalDraft(String(nextDashboard.schedule.interval_minutes));
    setSelectedResultIds((current) => current.filter((id) => nextDashboard.results.some((result) => result.id === id)));
    setApiOnline(true);
    setError("");
  }

  function getRequestError(caught: unknown, fallback: string) {
    const message = caught instanceof Error ? caught.message : fallback;
    if (message.startsWith("500 ") || message.toLowerCase().includes("failed to fetch")) {
      setApiOnline(false);
    }
    return message;
  }

  async function handleRefresh() {
    setIsRefreshing(true);
    setNotice("");
    setError("");
    try {
      await refreshDashboard();
      setNotice("Dashboard refreshed.");
    } catch (caught) {
      setError(getRequestError(caught, "Could not refresh dashboard."));
    } finally {
      setIsRefreshing(false);
    }
  }

  async function runNow(searchMode: "standard" | "detailed" = "standard") {
    const detailed = searchMode === "detailed";
    if (detailed) {
      setIsRunningDetailed(true);
    } else {
      setIsRunning(true);
    }
    setNotice("");
    setError("");
    try {
      const job = await apiRequest<FraudMonitorJob>("/fraud-monitor/jobs", {
        method: "POST",
        body: JSON.stringify({ search_mode: searchMode }),
      });
      await refreshDashboard();
      setNotice(
        job.status === "success"
          ? `${detailed ? "Detailed search" : "Free-provider scan"} stored ${job.result_count} fraud result(s).`
          : `${detailed ? "Detailed search" : "Fraud scan"} finished with ${job.status} status.`,
      );
    } catch (caught) {
      setError(getRequestError(caught, detailed ? "Could not run detailed search." : "Could not run fraud scan."));
    } finally {
      if (detailed) {
        setIsRunningDetailed(false);
      } else {
        setIsRunning(false);
      }
    }
  }

  async function downloadExport(format: "markdown" | "json") {
    setExportingFormat(format);
    setNotice("");
    setError("");
    try {
      const response = await fetch(`/api/backend/fraud-monitor/exports/${format}`, {
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = format === "markdown" ? "fraud-monitor-export.md" : "fraud-monitor-audit-bundle.json";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setNotice(format === "markdown" ? "Markdown export downloaded." : "JSON audit bundle downloaded.");
    } catch (caught) {
      setError(getRequestError(caught, "Could not download export."));
    } finally {
      setExportingFormat(null);
    }
  }

  async function updateSchedule(patch: SchedulePatch) {
    setIsSavingSchedule(true);
    setNotice("");
    setError("");
    try {
      await apiRequest("/fraud-monitor/schedule", {
        method: "PATCH",
        body: JSON.stringify(patch),
      });
      await refreshDashboard();
      setNotice("Schedule updated.");
    } catch (caught) {
      setError(getRequestError(caught, "Could not update schedule."));
    } finally {
      setIsSavingSchedule(false);
    }
  }

  async function saveInterval() {
    const intervalMinutes = Number.parseInt(intervalDraft, 10);
    if (!Number.isFinite(intervalMinutes)) {
      setError("Interval must be a number of minutes.");
      setNotice("");
      return;
    }
    await updateSchedule({ interval_minutes: intervalMinutes });
  }

  async function updateReviewStatus(result: NewsResultRecord, reviewStatus: NewsReviewStatus) {
    setNotice("");
    setError("");
    try {
      await apiRequest<NewsResultRecord>(`/fraud-monitor/results/${result.id}`, {
        method: "PATCH",
        body: JSON.stringify({ review_status: reviewStatus }),
      });
      await refreshDashboard();
      setNotice("Review status updated.");
    } catch (caught) {
      setError(getRequestError(caught, "Could not update review status."));
    }
  }

  async function applyResultControls() {
    const nextQuery: ResultQuery = {
      search: searchDraft,
      review: reviewFilter,
      provider: providerFilter,
      evidence: evidenceFilter,
      sort: resultSort,
      limit: resultLimit,
      offset: 0,
    };
    setIsRefreshing(true);
    setNotice("");
    setError("");
    try {
      setResultQuery(nextQuery);
      await refreshDashboard(nextQuery);
      setNotice("Review queue updated.");
    } catch (caught) {
      setError(getRequestError(caught, "Could not update review queue."));
    } finally {
      setIsRefreshing(false);
    }
  }

  async function goToResultPage(offset: number) {
    const nextQuery = { ...resultQuery, offset };
    setIsRefreshing(true);
    setNotice("");
    setError("");
    try {
      setResultQuery(nextQuery);
      await refreshDashboard(nextQuery);
    } catch (caught) {
      setError(getRequestError(caught, "Could not load result page."));
    } finally {
      setIsRefreshing(false);
    }
  }

  function toggleResultSelection(resultId: string) {
    setSelectedResultIds((current) =>
      current.includes(resultId)
        ? current.filter((id) => id !== resultId)
        : [...current, resultId],
    );
  }

  function togglePageSelection(checked: boolean) {
    setSelectedResultIds((current) => {
      if (!checked) {
        return current.filter((id) => !visibleResultIds.includes(id));
      }
      return Array.from(new Set([...current, ...visibleResultIds]));
    });
  }

  async function applyBulkReview() {
    if (selectedResultIds.length === 0) {
      return;
    }
    setNotice("");
    setError("");
    try {
      const response = await apiRequest<{ updated_count: number }>("/fraud-monitor/review-batches", {
        method: "PATCH",
        body: JSON.stringify({
          result_ids: selectedResultIds,
          review_status: bulkReviewStatus,
        }),
      });
      await refreshDashboard();
      setSelectedResultIds([]);
      setNotice(`Updated ${response.updated_count} selected result(s).`);
    } catch (caught) {
      setError(getRequestError(caught, "Could not update selected results."));
    }
  }

  async function saveEvidence(result: NewsResultRecord) {
    setNotice("");
    setError("");
    try {
      await apiRequest(`/fraud-monitor/results/${result.id}/evidence-links`, {
        method: "POST",
        body: JSON.stringify({ analyst_note: evidenceNotes[result.id] ?? "" }),
      });
      await refreshDashboard();
      setEvidenceNotes((current) => {
        const nextNotes = { ...current };
        delete nextNotes[result.id];
        return nextNotes;
      });
      setNotice("Evidence link saved.");
    } catch (caught) {
      setError(getRequestError(caught, "Could not save evidence link."));
    }
  }

  async function updateEvidenceNote(result: NewsResultRecord) {
    if (!result.evidence_link_id) {
      return;
    }
    setNotice("");
    setError("");
    try {
      await apiRequest(`/fraud-monitor/evidence-links/${result.evidence_link_id}`, {
        method: "PATCH",
        body: JSON.stringify({
          analyst_note: evidenceNotes[result.id] ?? result.evidence_analyst_note,
        }),
      });
      await refreshDashboard();
      setNotice("Evidence note updated.");
    } catch (caught) {
      setError(getRequestError(caught, "Could not update evidence note."));
    }
  }

  return (
    <div className="oc-app fm-app" data-theme="dark">
      <aside className="fm-rail" aria-label="Fraud monitor navigation">
        <a className="oc-brand" href="#monitor">
          <span className="oc-brand-mark" aria-hidden="true" />
          <span>Fraud Monitor</span>
        </a>
        <nav className="oc-nav" aria-label="Dashboard sections">
          <a className="oc-nav-link is-active" href="#monitor">
            Monitor
          </a>
          <a className="oc-nav-link" href="#results">
            Results
          </a>
          <a className="oc-nav-link" href="#jobs">
            Jobs
          </a>
        </nav>
        <div className={apiOnline ? "oc-badge oc-badge-success" : "oc-badge oc-badge-danger"}>
          API {apiOnline ? "online" : "unavailable"}
        </div>
      </aside>

      <main className="fm-main" id="monitor">
        <header className="fm-header">
          <div>
            <p className="oc-kicker">Fixed keyword</p>
            <h1>fraud</h1>
          </div>
          <div className="fm-header-actions">
            <button
              className="oc-btn oc-btn-primary"
              disabled={runDisabled}
              onClick={() => void runNow("standard")}
              type="button"
            >
              {isRunning || dashboard.runtime.is_running ? "Running" : "Run now"}
            </button>
            <button
              className="oc-btn"
              disabled={detailedDisabled}
              onClick={() => void runNow("detailed")}
              type="button"
            >
              {isRunningDetailed ? "Running detailed" : "Run detailed"}
            </button>
            <button className="oc-btn" disabled={isRefreshing} onClick={() => void handleRefresh()} type="button">
              {isRefreshing ? "Refreshing" : "Refresh"}
            </button>
            <button
              className="oc-btn"
              disabled={exportingFormat !== null}
              onClick={() => void downloadExport("markdown")}
              type="button"
            >
              {exportingFormat === "markdown" ? "Exporting" : "Export Markdown"}
            </button>
            <button
              className="oc-btn"
              disabled={exportingFormat !== null}
              onClick={() => void downloadExport("json")}
              type="button"
            >
              {exportingFormat === "json" ? "Exporting" : "Export JSON"}
            </button>
          </div>
        </header>

        {notice ? <div className="oc-callout oc-callout-info fm-message">{notice}</div> : null}
        {error ? <div className="oc-callout oc-callout-warning fm-message">{error}</div> : null}

        <section className="fm-stat-grid" aria-label="Fraud monitor counts">
          <Metric label="Stored results" value={dashboard.total_results} detail="All retained fraud matches" />
          <Metric label="Pending review" value={dashboard.pending_results} detail="Needs analyst decision" />
          <Metric label="Relevant" value={dashboard.relevant_results} detail="Marked useful" />
          <Metric label="Evidence links" value={dashboard.evidence_count} detail="Saved source records" />
          <Metric label="Vault artifacts" value={totalAvailableArtifacts} detail="Available on this page" />
        </section>

        <div className="fm-control-grid">
          <section className="oc-card fm-panel">
            <div className="oc-card-header">
              <div>
                <h2 className="oc-card-title">Job control</h2>
                <p className="oc-card-description">Manual and scheduled scans for one keyword.</p>
              </div>
              {dashboard.latest_job ? (
                <span className={statusClass(dashboard.latest_job.status)}>
                  {dashboard.latest_job.status}
                </span>
              ) : null}
            </div>
            <div className="oc-definition-list">
              <Definition
                label="Run state"
                value={dashboard.runtime.is_running ? "Running" : "Idle"}
              />
              <Definition label="Last run" value={compactDate(dashboard.schedule.last_completed_at)} />
              <Definition label="Next cron run" value={compactDate(dashboard.schedule.next_run_at)} />
              <Definition
                label="Interval"
                value={`${dashboard.schedule.interval_minutes} minutes`}
              />
              <Definition
                label="Ready providers"
                value={`${dashboard.runtime.ready_provider_count} provider(s)`}
              />
            </div>
            {dashboard.runtime.ready_provider_count === 0 ? (
              <p className="oc-empty-state">No ready providers are configured.</p>
            ) : null}
            {dashboard.runtime.last_error_message ? (
              <p className="oc-empty-state">
                Last provider issue: {dashboard.runtime.last_error_message}
                {dashboard.runtime.last_error_at ? ` (${compactDate(dashboard.runtime.last_error_at)})` : ""}
              </p>
            ) : null}
            <div className="fm-schedule-row">
              <label className="oc-check-row">
                <input
                  checked={dashboard.schedule.enabled}
                  disabled={isSavingSchedule}
                  onChange={(event) => void updateSchedule({ enabled: event.target.checked })}
                  type="checkbox"
                />
                Cron enabled
              </label>
              <label className="oc-field fm-interval-field">
                <span className="oc-label">Minutes</span>
                <input
                  className="oc-input"
                  max={1440}
                  min={5}
                  onChange={(event) => setIntervalDraft(event.target.value)}
                  type="number"
                  value={intervalDraft}
                />
              </label>
              <button className="oc-btn" disabled={isSavingSchedule} onClick={saveInterval} type="button">
                Save interval
              </button>
            </div>
          </section>

          <section className="oc-card fm-panel">
            <div className="oc-card-header">
              <div>
                <h2 className="oc-card-title">Providers</h2>
                <p className="oc-card-description">Free providers run by default.</p>
              </div>
              <span className={dashboard.configuration_validation.is_valid ? "oc-badge oc-badge-success" : "oc-badge oc-badge-danger"}>
                {dashboard.configuration_validation.is_valid ? "Config ok" : "Config attention"}
              </span>
            </div>
            <div className="oc-module-list">
              {dashboard.providers.map((provider) => (
                <ProviderRow key={provider.name} provider={provider} />
              ))}
              {showDetailedProvider ? <ProviderRow provider={dashboard.detailed_provider} /> : null}
              {dashboard.detailed_provider.status !== "ready" ? (
                <p className="oc-empty-state">Detailed search uses Brave only when the local API key is configured.</p>
              ) : null}
              {dashboard.configuration_validation.issues.map((issue) => (
                <div className="oc-module-row" key={`${issue.provider}:${issue.message}`}>
                  <div>
                    <strong>{issue.provider}</strong>
                    <p>{issue.message}</p>
                  </div>
                  <span className={issueClass(issue.severity)}>{issue.severity}</span>
                </div>
              ))}
              {dashboard.configuration_validation.issues.length === 0 ? (
                <p className="oc-empty-state">Configuration validation found no provider issues.</p>
              ) : null}
            </div>
          </section>

          <section className="oc-card fm-panel">
            <div className="oc-card-header">
              <div>
                <h2 className="oc-card-title">Trend groups</h2>
                <p className="oc-card-description">
                  {visibleTrends.length ? compactDate(dashboard.trend_summary.generated_at) : "No results yet"}
                </p>
              </div>
            </div>
            <div className="oc-module-list">
              {visibleTrends.length === 0 ? (
                <p className="oc-empty-state">Run a scan to build fraud trend groups.</p>
              ) : null}
              {visibleTrends.map((trend) => (
                <div className="oc-module-row" key={`${trend.group_type}:${trend.label}`}>
                  <div>
                    <strong>{trendLabel(trend)}</strong>
                    <p>{trend.priority_cue}</p>
                    <p>{trend.confidence_language}</p>
                  </div>
                  <span className="oc-badge oc-badge-info">{trend.result_count}</span>
                </div>
              ))}
            </div>
          </section>
        </div>

        <section className="oc-card fm-results" id="results">
          <div className="oc-card-header">
            <div>
              <h2 className="oc-card-title">Review queue</h2>
              <p className="oc-card-description">
                {dashboard.result_page.total_matching} matching result(s), {dashboard.total_results} stored
              </p>
            </div>
            <span className="oc-badge oc-badge-info">{sortLabel(dashboard.result_page.sort)}</span>
          </div>
          <div className="fm-filter-row" aria-label="Review queue filters">
            <label className="oc-field fm-search-field">
              <span className="oc-label">Search</span>
              <input
                className="oc-input"
                onChange={(event) => setSearchDraft(event.target.value)}
                placeholder="Title, source, category, state, theme"
                value={searchDraft}
              />
            </label>
            <label className="oc-field">
              <span className="oc-label">Review</span>
              <select
                className="oc-input"
                onChange={(event) => setReviewFilter(event.target.value as ReviewFilter)}
                value={reviewFilter}
              >
                <option value="all">All reviews</option>
                <option value="pending">Pending</option>
                <option value="relevant">Relevant</option>
                <option value="not_relevant">Not relevant</option>
              </select>
            </label>
            <label className="oc-field">
              <span className="oc-label">Provider</span>
              <select
                className="oc-input"
                onChange={(event) => setProviderFilter(event.target.value)}
                value={providerFilter}
              >
                <option value="all">All providers</option>
                {resultProviders.map((provider) => (
                  <option key={provider} value={provider}>
                    {providerLabel(provider)}
                  </option>
                ))}
              </select>
            </label>
            <label className="oc-field">
              <span className="oc-label">Evidence</span>
              <select
                className="oc-input"
                onChange={(event) => setEvidenceFilter(event.target.value as EvidenceFilter)}
                value={evidenceFilter}
              >
                <option value="all">All evidence states</option>
                <option value="saved">Saved evidence</option>
                <option value="unsaved">Unsaved</option>
              </select>
            </label>
            <label className="oc-field">
              <span className="oc-label">Sort</span>
              <select
                className="oc-input"
                onChange={(event) => setResultSort(event.target.value as ResultSort)}
                value={resultSort}
              >
                <option value="retrieved_desc">Retrieved newest</option>
                <option value="retrieved_asc">Retrieved oldest</option>
                <option value="published_desc">Published newest</option>
                <option value="published_asc">Published oldest</option>
                <option value="title_asc">Title A-Z</option>
                <option value="source_asc">Source A-Z</option>
                <option value="review_asc">Review status</option>
              </select>
            </label>
            <label className="oc-field fm-limit-field">
              <span className="oc-label">Page size</span>
              <select
                className="oc-input"
                onChange={(event) => setResultLimit(Number(event.target.value))}
                value={resultLimit}
              >
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </label>
            <button className="oc-btn" disabled={isRefreshing} onClick={() => void applyResultControls()} type="button">
              Apply
            </button>
          </div>

          <div className="fm-bulk-row" aria-label="Bulk review controls">
            <label className="oc-check-row">
              <input
                checked={visibleResultIds.length > 0 && selectedVisibleCount === visibleResultIds.length}
                disabled={visibleResultIds.length === 0}
                onChange={(event) => togglePageSelection(event.target.checked)}
                type="checkbox"
              />
              Select page
            </label>
            <label className="oc-field fm-bulk-status">
              <span className="oc-label">Set selected to</span>
              <select
                className="oc-input"
                onChange={(event) => setBulkReviewStatus(event.target.value as NewsReviewStatus)}
                value={bulkReviewStatus}
              >
                <option value="relevant">Relevant</option>
                <option value="not_relevant">Not relevant</option>
                <option value="pending">Pending</option>
              </select>
            </label>
            <button
              className="oc-btn oc-btn-primary"
              disabled={selectedResultIds.length === 0}
              onClick={() => void applyBulkReview()}
              type="button"
            >
              Apply to {selectedResultIds.length} selected
            </button>
          </div>
          <div className="fm-result-list">
            {dashboard.total_results === 0 ? (
              <p className="oc-empty-state">No fraud results are stored yet.</p>
            ) : null}
            {dashboard.total_results > 0 && dashboard.results.length === 0 ? (
              <p className="oc-empty-state">No results match the current filters.</p>
            ) : null}
            {dashboard.results.map((result) => (
              <article className="oc-panel fm-result" key={result.id}>
                <div className="fm-result-header">
                  <label className="fm-select-result" aria-label={`Select ${result.title || sourceSummary(result.source_url)}`}>
                    <input
                      checked={selectedResultIds.includes(result.id)}
                      onChange={() => toggleResultSelection(result.id)}
                      type="checkbox"
                    />
                  </label>
                  <div>
                    <div className="fm-result-badges">
                      <span className="oc-badge oc-badge-muted">{result.publisher || "Unknown source"}</span>
                      <span className={result.saved_as_evidence ? "oc-badge oc-badge-success" : "oc-badge oc-badge-muted"}>
                        {result.saved_as_evidence ? "Evidence saved" : "Unsaved"}
                      </span>
                      <span className={result.available_artifact_count > 0 ? "oc-badge oc-badge-success" : "oc-badge oc-badge-muted"}>
                        {result.available_artifact_count > 0
                          ? `${result.available_artifact_count} vault artifact(s)`
                          : "No local artifact"}
                      </span>
                      {result.duplicate_count > 0 ? (
                        <span className="oc-badge oc-badge-medium">Seen {result.seen_count} times</span>
                      ) : null}
                      <span className="oc-badge oc-badge-info">{result.recency_cue}</span>
                      <span className={result.source_quality === "named_source" ? "oc-badge oc-badge-success" : "oc-badge oc-badge-muted"}>
                        {result.source_quality === "named_source" ? "Named source" : "Source review"}
                      </span>
                      <span className="oc-badge oc-badge-info">Reported category: {result.classification_label}</span>
                      <span className={result.fraud_state_code ? "oc-badge oc-badge-info" : "oc-badge oc-badge-muted"}>
                        Reported state: {result.fraud_state_label || "Unknown"}
                      </span>
                    </div>
                    <h3>{result.title || sourceSummary(result.source_url)}</h3>
                  </div>
                  <span className={statusClass(result.review_status)}>
                    {result.review_status.replace("_", " ")}
                  </span>
                </div>
                <p>{result.snippet || "No snippet returned by the provider."}</p>
                <div className="oc-case-meta">
                  <span>Published {result.published_at || "unknown"}</span>
                  <span>Provider {result.provider ? providerLabel(result.provider) : "unknown"}</span>
                  <span>Retrieved {compactDate(result.retrieved_at)}</span>
                  <span>Theme {result.theme || "uncategorized"}</span>
                  <span>Basis {result.classification_basis}</span>
                  <span>State basis {result.fraud_state_basis}</span>
                </div>
                <p className="oc-empty-state">{result.prioritization_cue}</p>
                <div className="fm-source-row">
                  <span className="oc-technical" title={result.source_url}>
                    {sourceSummary(result.source_url)}
                  </span>
                  <a className="oc-btn oc-btn-sm" href={result.source_url} rel="noreferrer noopener" target="_blank">
                    Open source
                  </a>
                </div>
                {result.saved_as_evidence ? (
                  <div className="fm-artifact-list" aria-label="Evidence vault artifacts">
                    {result.evidence_artifacts.length === 0 ? (
                      <p className="oc-empty-state">Vault metadata has not been captured for this saved source.</p>
                    ) : null}
                    {result.evidence_artifacts.map((artifact) => (
                      <div className="fm-artifact-row" key={artifact.id}>
                        <div>
                          <strong>{artifactLabel(artifact.artifact_type)}</strong>
                          <p>
                            {artifact.availability === "available"
                              ? artifact.storage_path || artifact.source_url
                              : artifact.capture_note}
                          </p>
                          {artifact.content_hash ? (
                            <p className="oc-technical">sha256:{artifact.content_hash.slice(0, 16)}</p>
                          ) : null}
                        </div>
                        <span className={artifact.availability === "available" ? "oc-badge oc-badge-success" : "oc-badge oc-badge-muted"}>
                          {artifact.availability.replace("_", " ")}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : null}
                <div className="oc-row-actions">
                  {(["pending", "relevant", "not_relevant"] as NewsReviewStatus[]).map((status) => (
                    <button
                      className="oc-btn oc-btn-sm"
                      disabled={result.review_status === status}
                      key={status}
                      onClick={() => void updateReviewStatus(result, status)}
                      type="button"
                    >
                      {status.replace("_", " ")}
                    </button>
                  ))}
                  <button
                    className="oc-btn oc-btn-primary oc-btn-sm"
                    disabled={result.saved_as_evidence}
                    onClick={() => void saveEvidence(result)}
                    type="button"
                  >
                    {result.saved_as_evidence ? "Saved" : "Save evidence"}
                  </button>
                </div>
                <div className="fm-note-row">
                  <label className="oc-field">
                    <span className="oc-label">
                      {result.saved_as_evidence ? "Saved evidence note" : "Analyst note"}
                    </span>
                    <textarea
                      className="oc-input fm-note-input"
                      onChange={(event) =>
                        setEvidenceNotes((current) => ({
                          ...current,
                          [result.id]: event.target.value,
                        }))
                      }
                      placeholder={result.saved_as_evidence ? "Update saved context" : "Add context before saving evidence"}
                      value={evidenceNotes[result.id] ?? result.evidence_analyst_note}
                    />
                  </label>
                  {result.saved_as_evidence ? (
                    <button className="oc-btn oc-btn-sm" onClick={() => void updateEvidenceNote(result)} type="button">
                      Update note
                    </button>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
          <div className="fm-pagination-row">
            <button
              className="oc-btn"
              disabled={!dashboard.result_page.has_previous || isRefreshing}
              onClick={() => void goToResultPage(Math.max(0, dashboard.result_page.offset - dashboard.result_page.limit))}
              type="button"
            >
              Previous
            </button>
            <span>
              Showing {dashboard.result_page.total_matching === 0 ? 0 : dashboard.result_page.offset + 1}-
              {Math.min(dashboard.result_page.offset + dashboard.result_page.limit, dashboard.result_page.total_matching)}
            </span>
            <button
              className="oc-btn"
              disabled={!dashboard.result_page.has_next || isRefreshing}
              onClick={() => void goToResultPage(dashboard.result_page.offset + dashboard.result_page.limit)}
              type="button"
            >
              Next
            </button>
          </div>
        </section>

        <section className="oc-card fm-panel" id="jobs">
          <div className="oc-card-header">
            <div>
              <h2 className="oc-card-title">Job history</h2>
              <p className="oc-card-description">Recent on-demand and cron runs.</p>
            </div>
          </div>
          <div className="fm-job-list">
            {dashboard.jobs.length === 0 ? (
              <p className="oc-empty-state">No fraud jobs have run yet.</p>
            ) : null}
            {dashboard.jobs.map((job) => (
              <div className="oc-module-row" key={job.id}>
                <div>
                  <strong>{job.trigger_type} scan</strong>
                  <p>
                    {job.result_count} result(s) from{" "}
                    {job.provider_runs.length
                      ? job.provider_runs.map(providerLabel).join(", ")
                      : `${job.provider_count} provider(s)`}
                  </p>
                  {job.error_message ? <p>{job.error_message}</p> : null}
                  {job.provider_run_summaries.map((summary) => (
                    <p key={`${job.id}:${summary.provider}`}>
                      {providerLabel(summary.provider)} stored {summary.stored_result_count} of{" "}
                      {summary.raw_result_count} returned result(s). {summary.note}
                    </p>
                  ))}
                </div>
                <span className={statusClass(job.status)}>{job.status}</span>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

function Metric({ label, value, detail }: { label: string; value: number; detail: string }) {
  return (
    <div className="oc-stat-card">
      <span className="oc-stat-label">{label}</span>
      <div className="oc-stat-value">{value}</div>
      <div className="oc-stat-trend">{detail}</div>
    </div>
  );
}

function Definition({ label, value }: { label: string; value: string }) {
  return (
    <div className="oc-definition-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ProviderRow({ provider }: { provider: ProviderInfo }) {
  return (
    <div className="oc-module-row">
      <div>
        <strong>{providerLabel(provider.name)}</strong>
        <p>{provider.note}</p>
        <p>
          {provider.request_limit} Timeout {provider.timeout_seconds}s.
          {provider.last_run_status
            ? ` Last run ${provider.last_run_status}, ${provider.last_result_count} result(s).`
            : ""}
          {provider.next_retry_at ? ` Retry after ${compactDate(provider.next_retry_at)}.` : ""}
        </p>
        {provider.last_error_message ? <p>{provider.last_error_message}</p> : null}
      </div>
      <span className={statusClass(provider.status)}>{provider.status.replace("_", " ")}</span>
    </div>
  );
}
