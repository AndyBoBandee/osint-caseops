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

Represents one module execution.

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
