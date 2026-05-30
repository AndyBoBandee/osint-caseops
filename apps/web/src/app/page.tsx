type HealthResponse = {
  status: string;
  service?: string;
};

async function getApiHealth(): Promise<HealthResponse> {
  const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";

  try {
    const response = await fetch(`${apiBaseUrl}/health`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return { status: "unavailable" };
    }

    return response.json() as Promise<HealthResponse>;
  } catch {
    return { status: "unavailable" };
  }
}

const workflowSteps = [
  ["Scope", "Start each case with a lawful public-source boundary."],
  ["Entity", "Add a domain or URL for passive review."],
  ["Evidence", "Preserve source context, timestamps, and screenshots."],
  ["Report", "Export findings with confidence and methodology."],
];

const docs = [
  "docs/project/scope.md",
  "docs/product/mvp.md",
  "docs/security/responsible-use.md",
];

export default async function Home() {
  const health = await getApiHealth();
  const apiOnline = health.status === "ok";

  return (
    <main className="page-shell">
      <div className="workspace">
        <section>
          <div className="hero">
            <h1>OSINT CaseOps</h1>
            <p>
              A local-first case workbench for ethical public-source investigations,
              starting with passive domain and URL review.
            </p>
          </div>

          <div className="section">
            <h2>MVP Workflow</h2>
            <ul className="flow-list">
              {workflowSteps.map(([title, description]) => (
                <li key={title}>
                  <strong>{title}</strong>
                  <span>{description}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <aside className="panel" aria-label="Foundation status">
          <h2>Foundation Status</h2>
          <div className={apiOnline ? "status-pill" : "status-pill warning"}>
            API {apiOnline ? "online" : "unavailable"}
          </div>

          <div className="section">
            <ul className="status-list">
              <li className="status-item">
                <strong>Web</strong>
                <span>Next.js scaffold</span>
              </li>
              <li className="status-item">
                <strong>API</strong>
                <span>{health.service ?? "FastAPI health check"}</span>
              </li>
              <li className="status-item">
                <strong>Storage</strong>
                <span>SQLite local-first path</span>
              </li>
            </ul>
          </div>

          <div className="doc-links" aria-label="Project documents">
            {docs.map((doc) => (
              <code key={doc}>{doc}</code>
            ))}
          </div>
        </aside>
      </div>
    </main>
  );
}
