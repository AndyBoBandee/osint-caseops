import { CaseDashboard, type CaseSummary } from "./case-dashboard";

type HealthResponse = {
  status: string;
  service?: string;
};

const apiBaseUrl = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

async function getApiJson<T>(path: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return fallback;
    }

    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

export default async function Home() {
  const [health, cases] = await Promise.all([
    getApiJson<HealthResponse>("/health", { status: "unavailable" }),
    getApiJson<CaseSummary[]>("/cases", []),
  ]);

  return (
    <div className="oc-app oc-app-horizontal" data-theme="dark">
      <aside className="oc-sidebar oc-menu-bar" aria-label="Primary">
        <a className="oc-brand" href="#dashboard">
          <span className="oc-brand-mark" aria-hidden="true" />
          <span>OSINT CaseOps</span>
        </a>
        <nav className="oc-nav" aria-label="Workspace sections">
          <a className="oc-nav-link is-active" href="#dashboard">
            Dashboard
          </a>
          <a className="oc-nav-link" href="#case-detail">
            Case Detail
          </a>
          <a className="oc-nav-link" href="#entity-profile">
            Entity Profile
          </a>
          <a className="oc-nav-link" href="#evidence-viewer">
            Evidence
          </a>
          <a className="oc-nav-link" href="#relationship-graph">
            Graph
          </a>
          <a className="oc-nav-link" href="#report-preview">
            Report
          </a>
        </nav>
        <div
          className={
            health.status === "ok"
              ? "oc-badge oc-badge-success oc-system-status"
              : "oc-badge oc-badge-medium oc-system-status"
          }
        >
          API {health.status === "ok" ? "online" : "unavailable"}
        </div>
      </aside>

      <main className="oc-main">
        <div className="oc-main-inner">
          <header className="oc-topbar">
            <div className="oc-page-header">
              <h1 className="oc-page-title">Case workbench</h1>
              <p className="oc-page-subtitle">
                Scoped public-source research, evidence tracking, relationship review, and
                report drafting in one local workspace.
              </p>
            </div>
            <a className="oc-btn oc-btn-primary" href="#case-detail">
              New case
            </a>
          </header>

          <CaseDashboard initialCases={cases} initialApiOnline={health.status === "ok"} />
        </div>
      </main>
    </div>
  );
}
