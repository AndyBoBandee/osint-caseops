# MVP Definition

## MVP Thesis

Fraud Monitor should prove one complete local-first workflow: run on-demand and scheduled public-source jobs for the fixed keyword `fraud`, store results locally, support analyst review, save source links as evidence, and let analysts write findings with timeline context.

The broader OSINT CaseOps case, entity, relationship graph, and hosted report workflow is legacy product direction unless explicitly reintroduced.

## Primary User

The primary user is an analyst, researcher, or technically comfortable operator who wants a focused review queue for public fraud reporting without using a hosted investigation platform.

## Core User Journey

1. User opens the Fraud Monitor dashboard.
2. User checks provider readiness.
3. User runs a scan or enables the local scheduler.
4. System stores provider runs and returned public results.
5. User reviews results and marks relevance.
6. User saves useful source links as evidence.
7. User writes confidence-aware findings linked to saved evidence.
8. User reviews trend groups, job history, and timeline events.
9. User exports reviewed local data as Markdown or JSON.

## Required MVP Surface

- Fraud Monitor dashboard.
- Manual run control.
- Schedule control.
- Provider status.
- Result review queue.
- Evidence-link action.
- Findings workspace.
- Timeline history.
- Job history.
- Trend groups.
- Provider configuration validation.
- Local Markdown and JSON exports.
- Responsible-use documentation.

## Acceptance Criteria

The MVP is complete when a user can run the app locally, perform a fraud monitor scan, inspect provider/job status, review stored public results, save an evidence link, write an analyst-authored finding, export reviewed local data, and verify all data remains local. Findings must remain analyst-authored and confidence-aware.
