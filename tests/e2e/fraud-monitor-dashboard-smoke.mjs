import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, "../..");
const apiDir = path.join(repoRoot, "apps/api");
const webDir = path.join(repoRoot, "apps/web");
const { chromium } = require(path.join(webDir, "node_modules/playwright"));

const apiUrl = process.env.OSINT_CASEOPS_E2E_API_URL ?? "http://127.0.0.1:8000";
const webUrl = process.env.OSINT_CASEOPS_E2E_WEB_URL ?? "http://127.0.0.1:3000";
const apiPort = new URL(apiUrl).port || "8000";
const webPort = new URL(webUrl).port || "3000";

const children = [];
const logs = new Map();
let dataDir = "";

function rememberLog(name, chunk) {
  const current = logs.get(name) ?? "";
  logs.set(name, `${current}${chunk.toString()}`.slice(-8000));
}

function startProcess(name, command, args, options) {
  const child = spawn(command, args, {
    ...options,
    detached: true,
    stdio: ["ignore", "pipe", "pipe"],
  });
  children.push(child);
  logs.set(name, "");
  child.stdout.on("data", (chunk) => rememberLog(name, chunk));
  child.stderr.on("data", (chunk) => rememberLog(name, chunk));
  return child;
}

async function stopProcess(child) {
  if (child.exitCode !== null || child.signalCode !== null) {
    return;
  }
  try {
    process.kill(-child.pid, "SIGTERM");
  } catch {
    return;
  }
  await new Promise((resolve) => {
    const timeout = setTimeout(resolve, 2500);
    child.once("exit", () => {
      clearTimeout(timeout);
      resolve();
    });
  });
  if (child.exitCode === null && child.signalCode === null) {
    try {
      process.kill(-child.pid, "SIGKILL");
    } catch {
      // Process already ended.
    }
  }
}

async function cleanup() {
  await Promise.all(children.map((child) => stopProcess(child)));
  if (dataDir) {
    await rm(dataDir, { force: true, recursive: true });
  }
}

async function waitForUrl(url, label) {
  const deadline = Date.now() + 60_000;
  let lastError = "";
  while (Date.now() < deadline) {
    for (const child of children) {
      if (child.exitCode !== null) {
        throw new Error(`${label} startup failed because a child process exited early.`);
      }
    }
    try {
      const response = await fetch(url);
      if (response.ok) {
        return;
      }
      lastError = `${response.status} ${response.statusText}`;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`${label} did not become ready at ${url}: ${lastError}`);
}

async function expectVisible(locator, label) {
  await locator.first().waitFor({ state: "visible", timeout: 15_000 }).catch((error) => {
    throw new Error(`Expected visible ${label}: ${error.message}`);
  });
}

async function main() {
  dataDir = await mkdtemp(path.join(tmpdir(), "osint-caseops-e2e-"));
  startProcess(
    "api",
    "uv",
    ["run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", apiPort],
    {
      cwd: apiDir,
      env: {
        ...process.env,
        OSINT_CASEOPS_DATA_DIR: dataDir,
        OSINT_CASEOPS_ENABLE_FIXTURE_PROVIDER: "1",
        OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS: "fixture",
        BRAVE_SEARCH_API_KEY: "",
      },
    },
  );
  startProcess("web", "npm", ["run", "dev", "--", "--hostname", "127.0.0.1", "--port", webPort], {
    cwd: webDir,
    env: {
      ...process.env,
      API_BASE_URL: apiUrl,
      NEXT_TELEMETRY_DISABLED: "1",
    },
  });

  await waitForUrl(`${apiUrl}/health`, "API");
  await waitForUrl(webUrl, "web app");

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 980 } });
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));

  try {
    await page.goto(webUrl, { waitUntil: "networkidle" });
    await expectVisible(page.getByRole("heading", { name: "fraud" }), "Fraud Monitor heading");
    await expectVisible(page.getByText("Config ok"), "configuration status");
    await expectVisible(page.getByText("Fixture"), "fixture provider");
    await expectVisible(page.getByRole("button", { name: "Run now" }), "run button");
    await expectVisible(page.getByRole("button", { name: "Export Markdown" }), "Markdown export button");
    await expectVisible(page.getByRole("button", { name: "Export JSON" }), "JSON export button");

    await Promise.all([
      page.waitForResponse(
        (response) => response.url().includes("/api/backend/fraud-monitor/jobs") && response.status() < 500,
      ),
      page.getByRole("button", { name: "Run now" }).click(),
    ]);
    await expectVisible(page.getByText("Free-provider scan stored 2 fraud result(s)."), "run completion notice");
    await expectVisible(page.getByText("Public lending fraud reporting fixture"), "first source card title");
    await expectVisible(page.getByText("Agency fraud warning fixture"), "second source card title");
    await expectVisible(page.getByText("Reported category: lending fraud"), "reported category badge");
    await expectVisible(page.getByText("Reported state: Unknown"), "reported state badge");
    await expectVisible(page.getByText("fixture.example/public-fraud-reporting"), "short source location");

    const sourceHrefs = await page
      .getByRole("link", { name: "Open source" })
      .evaluateAll((links) => links.map((link) => link.getAttribute("href")));
    if (!sourceHrefs.includes("https://fixture.example/public-fraud-reporting")) {
      throw new Error(`Expected source links to preserve fixture URL, got ${sourceHrefs.join(", ")}`);
    }
    await Promise.all([
      page.waitForResponse(
        (response) => response.url().includes("/api/backend/fraud-monitor/results/") && response.status() < 500,
      ),
      page.getByRole("button", { name: "Save evidence" }).first().click(),
    ]);
    await expectVisible(page.getByText("Evidence link saved."), "evidence saved notice");
    await expectVisible(page.getByText("2 vault artifact(s)"), "vault artifact badge");
    await expectVisible(page.getByText("Text snapshot"), "text snapshot artifact");
    await expectVisible(page.getByText("Source URL"), "source URL artifact");
    await expectVisible(page.getByRole("heading", { name: "Findings workspace" }), "findings workspace");

    await page.getByRole("textbox", { name: "Title" }).fill("Analyst-authored fixture finding");
    await page.getByLabel("Summary").fill("Reviewed fixture evidence supports a cautious follow-up lead.");
    await page.getByRole("combobox", { name: "Confidence", exact: true }).selectOption("medium");
    await page.getByRole("combobox", { name: "Status", exact: true }).selectOption("active");
    await page.getByLabel("Analyst notes").fill("No automated fraud verdict is asserted.");
    await page.getByRole("checkbox", { name: "Public lending fraud reporting fixture", exact: true }).check();
    await Promise.all([
      page.waitForResponse(
        (response) => response.url().includes("/api/backend/fraud-monitor/findings") && response.status() === 201,
      ),
      page.getByRole("button", { name: "Save finding" }).click(),
    ]);
    await expectVisible(page.getByText("Finding saved: Analyst-authored fixture finding"), "finding saved notice");
    await expectVisible(page.getByText("Reviewed fixture evidence supports a cautious follow-up lead."), "saved finding summary");
    await expectVisible(page.getByRole("heading", { name: "Timeline" }), "timeline section");
    await expectVisible(page.getByText("Finding created"), "finding timeline event");

    await page.getByLabel("Search").fill("Agency");
    await Promise.all([
      page.waitForResponse(
        (response) => response.url().includes("/api/backend/fraud-monitor/dashboard") && response.status() === 200,
      ),
      page.getByRole("button", { name: "Apply", exact: true }).click(),
    ]);
    await expectVisible(page.getByText("1 matching result(s), 2 stored"), "filtered result count");
    await expectVisible(page.getByText("Agency fraud warning fixture"), "filtered source card");

    await page.getByLabel("Select page").check();
    await expectVisible(page.getByRole("button", { name: "Apply to 1 selected" }), "selected bulk action");
  } finally {
    await browser.close();
  }

  if (consoleErrors.length > 0) {
    throw new Error(`Browser console errors:\n${consoleErrors.join("\n")}`);
  }

  console.log("Rendered Fraud Monitor e2e smoke passed.");
}

try {
  await main();
} catch (error) {
  console.error(error instanceof Error ? error.stack || error.message : error);
  for (const [name, output] of logs.entries()) {
    if (output.trim()) {
      console.error(`\n--- ${name} logs ---\n${output}`);
    }
  }
  process.exitCode = 1;
} finally {
  await cleanup();
}
