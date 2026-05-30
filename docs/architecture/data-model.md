# Data Model

## Case

Represents a scoped investigation.

Fields:

- id.
- title.
- objective.
- scope_category.
- scope_notes.
- case_type.
- status.
- created_at.
- updated_at.
- tags.
- analyst_notes.

## Entity

Represents an item under investigation.

Fields:

- id.
- case_id.
- type.
- value.
- display_name.
- description.
- confidence.
- created_at.
- updated_at.
- tags.

MVP entity types:

- domain.
- url.
- email.
- ip_address.
- organization.

## Evidence

Represents preserved support for a finding or case note.

Fields:

- id.
- case_id.
- source_url.
- title.
- captured_at.
- screenshot_path.
- html_path.
- archive_url.
- source_reliability.
- notes.
- hash.
- created_at.
- updated_at.

Evidence should support linking to multiple entities and findings through join tables.

## Finding

Represents an analyst claim or generated observation.

Fields:

- id.
- case_id.
- title.
- summary.
- confidence.
- severity.
- source_count.
- manual_verification_status.
- created_at.
- updated_at.
- analyst_notes.

Confidence values:

- high.
- medium.
- low.
- unknown.

Severity values:

- informational.
- low.
- medium.
- high.
- critical.

## Relationship

Represents a typed connection between two case objects.

Fields:

- id.
- case_id.
- source_type.
- source_id.
- target_type.
- target_id.
- relationship_type.
- confidence.
- evidence_id.
- notes.
- created_at.

## Enrichment Run

Represents one passive enrichment execution for an entity. Module-level results are stored inside
`result_json` so a run can show both successful modules and failed modules together.

Fields:

- id.
- case_id.
- entity_id.
- module_name.
- status.
- started_at.
- completed_at.
- result_json.
- error_message.

## News Keyword Set

Represents scoped terms for public news or search monitoring.

Fields:

- id.
- case_id.
- name.
- keywords.
- scope_notes.
- created_at.
- updated_at.

## News Ingestion Run

Represents one public news or search provider request batch for a case.

Fields:

- id.
- case_id.
- keyword_set_id.
- provider.
- status.
- started_at.
- completed_at.
- query_keywords.
- result_count.
- error_message.
- created_at.

## News Result

Represents one stored public news or search result awaiting analyst review.

Fields:

- id.
- case_id.
- run_id.
- keyword.
- source_url.
- publisher.
- title.
- snippet.
- published_at.
- retrieved_at.
- review_status.
- saved_as_evidence.
- evidence_link_id.
- theme.
- created_at.

## Evidence Link

Represents a milestone 4 source-link evidence record saved from the news review queue. Full evidence
artifacts arrive in the evidence capture milestone.

Fields:

- id.
- case_id.
- news_result_id.
- source_url.
- publisher.
- title.
- snippet.
- published_at.
- retrieved_at.
- query_keyword.
- analyst_note.
- created_at.

## Timeline Event

Represents important case activity.

Fields:

- id.
- case_id.
- event_type.
- title.
- description.
- object_type.
- object_id.
- occurred_at.
- metadata_json.

## Report Export

Represents a generated report.

Fields:

- id.
- case_id.
- format.
- output_path.
- generated_at.
- included_sections_json.
- hash.
