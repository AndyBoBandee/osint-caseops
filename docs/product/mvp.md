# MVP Definition

## MVP Thesis

Fraud Monitor should prove one complete local-first workflow: run on-demand and scheduled public-source jobs for the fixed keyword `fraud`, store results locally, support analyst review, and save source links as evidence.

The broader OSINT CaseOps case, entity, relationship, timeline, and report workflow is legacy product direction unless explicitly reintroduced.

## Primary User

The primary user is an analyst, researcher, or technically comfortable operator who wants a focused review queue for public fraud reporting without using a hosted investigation platform.

## Core User Journey

1. User opens the Fraud Monitor dashboard.
2. User checks provider readiness.
3. User runs a scan or enables the local scheduler.
4. System stores provider runs and returned public results.
5. User reviews results and marks relevance.
6. User saves useful source links as evidence.
7. User reviews trend groups and job history.

## Required MVP Surface

- Fraud Monitor dashboard.
- Manual run control.
- Schedule control.
- Provider status.
- Result review queue.
- Evidence-link action.
- Job history.
- Trend groups.
- Responsible-use documentation.

## Acceptance Criteria

The MVP is complete when a user can run the app locally, perform a fraud monitor scan, inspect provider/job status, review stored public results, save an evidence link, and verify all data remains local.
