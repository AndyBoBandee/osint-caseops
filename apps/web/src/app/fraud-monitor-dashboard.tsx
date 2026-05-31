"use client";

import { useMemo, useState } from "react";

import { apiRequest } from "./case-api";
import {
  FraudMonitorDashboardData,
  FraudMonitorJob,
  NewsResultRecord,
  NewsReviewStatus,
  ProviderInfo,
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

function statusClass(status: string) {
  if (status === "success" || status === "ready" || status === "relevant") {
    return "oc-badge oc-badge-success";
  }
  if (status === "partial" || status === "needs_key" || status === "pending") {
    return "oc-badge oc-badge-medium";
  }
  if (status === "not_relevant") {
    return "oc-badge oc-badge-muted";
  }
  return "oc-badge oc-badge-danger";
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
  if (provider === "brave") {
    return "Brave";
  }
  return provider.replaceAll("_", " ");
}

function trendLabel(group: TrendGroup) {
  return `${group.group_type.replaceAll("_", " ")}: ${group.label}`;
}

export function FraudMonitorDashboard({
  initialDashboard,
  initialApiOnline,
}: FraudMonitorDashboardProps) {
  const [dashboard, setDashboard] = useState(initialDashboard);
  const [isRunning, setIsRunning] = useState(false);
  const [isSavingSchedule, setIsSavingSchedule] = useState(false);
  const [intervalDraft, setIntervalDraft] = useState(
    String(initialDashboard.schedule.interval_minutes),
  );
  const [notice, setNotice] = useState("");
  const [error, setError] = useState(initialApiOnline ? "" : "Start the API to run fraud scans.");

  const visibleTrends = useMemo(
    () => dashboard.trend_summary.groups.slice(0, 6),
    [dashboard.trend_summary.groups],
  );

  async function refreshDashboard() {
    const nextDashboard = await apiRequest<FraudMonitorDashboardData>("/fraud-monitor/dashboard");
    setDashboard(nextDashboard);
    setIntervalDraft(String(nextDashboard.schedule.interval_minutes));
  }

  async function runNow() {
    setIsRunning(true);
    setNotice("");
    setError("");
    try {
      const job = await apiRequest<FraudMonitorJob>("/fraud-monitor/jobs", { method: "POST" });
      await refreshDashboard();
      setNotice(
        job.status === "success"
          ? `Stored ${job.result_count} fraud result(s).`
          : `Fraud scan finished with ${job.status} status.`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not run fraud scan.");
    } finally {
      setIsRunning(false);
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
      setError(caught instanceof Error ? caught.message : "Could not update schedule.");
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
      setError(caught instanceof Error ? caught.message : "Could not update review status.");
    }
  }

  async function saveEvidence(result: NewsResultRecord) {
    setNotice("");
    setError("");
    try {
      await apiRequest(`/fraud-monitor/results/${result.id}/evidence-links`, {
        method: "POST",
        body: JSON.stringify({ analyst_note: "Saved from the fraud monitor review queue." }),
      });
      await refreshDashboard();
      setNotice("Evidence link saved.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save evidence link.");
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
        <div className={initialApiOnline ? "oc-badge oc-badge-success" : "oc-badge oc-badge-danger"}>
          API {initialApiOnline ? "online" : "unavailable"}
        </div>
      </aside>

      <main className="fm-main" id="monitor">
        <header className="fm-header">
          <div>
            <p className="oc-kicker">Fixed keyword</p>
            <h1>fraud</h1>
          </div>
          <div className="fm-header-actions">
            <button className="oc-btn oc-btn-primary" disabled={isRunning} onClick={runNow} type="button">
              {isRunning ? "Running" : "Run now"}
            </button>
            <button className="oc-btn" onClick={() => void refreshDashboard()} type="button">
              Refresh
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
              <Definition label="Last run" value={compactDate(dashboard.schedule.last_completed_at)} />
              <Definition label="Next cron run" value={compactDate(dashboard.schedule.next_run_at)} />
              <Definition
                label="Interval"
                value={`${dashboard.schedule.interval_minutes} minutes`}
              />
            </div>
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
                <p className="oc-card-description">No-key providers run by default.</p>
              </div>
            </div>
            <div className="oc-module-list">
              {dashboard.providers.map((provider) => (
                <ProviderRow key={provider.name} provider={provider} />
              ))}
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
              <p className="oc-card-description">{dashboard.results.length} recent stored result(s)</p>
            </div>
          </div>
          <div className="fm-result-list">
            {dashboard.results.length === 0 ? (
              <p className="oc-empty-state">No fraud results are stored yet.</p>
            ) : null}
            {dashboard.results.map((result) => (
              <article className="oc-panel fm-result" key={result.id}>
                <div className="fm-result-header">
                  <div>
                    <span className="oc-badge oc-badge-muted">{result.publisher || "Unknown source"}</span>
                    <h3>{result.title || result.source_url}</h3>
                  </div>
                  <span className={statusClass(result.review_status)}>
                    {result.review_status.replace("_", " ")}
                  </span>
                </div>
                <p>{result.snippet || "No snippet returned by the provider."}</p>
                <div className="oc-case-meta">
                  <span>Published {result.published_at || "unknown"}</span>
                  <span>Retrieved {compactDate(result.retrieved_at)}</span>
                  <span>Theme {result.theme || "uncategorized"}</span>
                </div>
                <a className="oc-technical" href={result.source_url} rel="noreferrer" target="_blank">
                  {result.source_url}
                </a>
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
              </article>
            ))}
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
      </div>
      <span className={statusClass(provider.status)}>{provider.status.replace("_", " ")}</span>
    </div>
  );
}
