# Fraud Monitor Vision

## Purpose

Fraud Monitor is a local-first dashboard for passive public-source monitoring of the fixed keyword `fraud`. It helps analysts run visible provider jobs, review returned sources, and save useful links as evidence without sending case data to a hosted service.

## Mission

Help analysts monitor public fraud reporting in a calm, repeatable, evidence-first workflow.

## Vision

Fraud monitoring should be transparent, source-attributed, and reviewable. The product should make provider runs, stored results, analyst decisions, and limitations easy to inspect.

## Product Direction

The first product version focuses on one concrete workflow:

- Run on-demand public searches for `fraud`.
- Enable or disable a local scheduled monitor while the API process is running.
- Store runs, results, review status, trend groups, and evidence links in local SQLite.
- Keep provider status and errors visible.
- Require analyst review before treating public results as useful evidence.

The broader OSINT CaseOps case-management idea is legacy direction unless it is explicitly reintroduced into the Fraud Monitor roadmap.

## Values

- Ethical by design.
- Passive public-source methods.
- Evidence over assumption.
- Local-first privacy.
- Clear source attribution.
- Human review before conclusions.
