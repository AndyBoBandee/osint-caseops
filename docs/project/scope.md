# Project Scope

## In Scope

Fraud Monitor provides a focused, local-first workflow for passive public-source monitoring of the fixed keyword `fraud`.

Core capabilities:

- Manual fraud monitor runs.
- One active run at a time.
- Local scheduler controls while the API process is running.
- Passive public provider searches.
- Provider status and job history.
- Stored result review.
- Review statuses: pending, relevant, and not relevant.
- Evidence-link saving with analyst notes.
- Basic trend grouping by keyword, source, time window, and repeated theme.
- Local SQLite storage.
- Responsible-use guidance for passive public-source research.
- Deterministic fixture-provider smoke tests that make no external requests.

## Out Of Scope

These features are out of scope for the current Fraud Monitor foundation:

- Automated fraud verdicts without analyst review and cited evidence.
- Private-individual profiling.
- Credential, password, or secret harvesting.
- Dark web scraping.
- Exploit scanning or vulnerability exploitation.
- Login-protected scraping.
- Active checks against third-party systems.
- Phone-number enrichment.
- Social username enumeration.
- Breach-data searching.
- Cloud sync or multi-user collaboration.

## Success Criteria

The current slice is successful when a user can:

- Start the app locally.
- See the Fraud Monitor dashboard as the first screen.
- Run a fraud scan across configured ready providers.
- Enable or disable scheduled local scans.
- Review stored public results.
- Mark results relevant or not relevant.
- Save a source as evidence.
- See provider, job, and trend context without leaving the app.
