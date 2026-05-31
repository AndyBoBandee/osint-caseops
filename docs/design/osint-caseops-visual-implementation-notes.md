# Fraud Monitor Visual Implementation Notes

Use this alongside the existing `osint-caseops.css` stylesheet name and the UI mockup image. The stylesheet filename is a stable technical artifact; Fraud Monitor is the active product brand.

## Visual Direction

The UI should feel like a calm intelligence workbench, not a plain admin panel and not a hacker-themed toy.

Use:

- Dark navy/slate backgrounds
- Soft glassy cards
- Cyan signal accents
- Green/amber/red only for meaningful confidence or severity
- Rounded 2xl cards
- Subtle borders
- Strong spacing
- Graph/timeline/report views that feel like investigation software

Avoid:

- Plain black and white only
- Default browser controls
- Neon overload
- Skull/mask/crosshair imagery
- Aggressive terms like target, hunt, exploit, weaponize
- Unsupported “malicious” claims without confidence and evidence

## App Shell Requirements

The main layout should include:

1. Left sidebar navigation
2. Sticky topbar
3. Dashboard cards
4. Case detail view
5. Entity profile view
6. Evidence viewer
7. Relationship graph
8. Report preview

## Key UI Components

Use these classes from the stylesheet:

- `.oc-app`
- `.oc-sidebar`
- `.oc-brand`
- `.oc-nav-link`
- `.oc-main`
- `.oc-topbar`
- `.oc-card`
- `.oc-stat-card`
- `.oc-btn`
- `.oc-btn-primary`
- `.oc-badge`
- `.oc-badge-high`
- `.oc-badge-medium`
- `.oc-badge-low`
- `.oc-badge-danger`
- `.oc-table`
- `.oc-tabs`
- `.oc-evidence-layout`
- `.oc-graph`
- `.oc-timeline`
- `.oc-report-layout`
- `.oc-report-page`

## Theme

Set the default app root to:

```html
<div class="oc-app" data-theme="dark">
```

Add a future light mode toggle by switching:

```html
data-theme="light"
```

## Typography

Use Inter for interface text and JetBrains Mono for technical values.

Technical values include:

- Domains
- URLs
- IP addresses
- DNS records
- JSON
- Hashes
- File paths
- Timestamps

## Dashboard Layout

Dashboard should include:

- Active cases
- Entities tracked
- Findings
- Evidence items
- Alerts
- Recent cases table
- Findings by confidence
- Recent alerts
- Timeline activity

## Case Detail Layout

Case detail should include:

- Case title
- Case type
- Status badge
- Created/updated dates
- Tabs for Summary, Entities, Findings, Evidence, Relationships, Timeline, Notes
- Relationship graph
- Key stats

## Entity Profile Layout

Entity page should include:

- Entity value
- Type badge
- Follow/watch action
- Entity summary card
- Enrichment summary card
- Findings linked to the entity
- Evidence linked to the entity
- Relationships
- Notes

## Evidence Viewer Layout

Evidence viewer should include:

- Large screenshot/document preview
- Evidence details sidebar
- Source URL
- Capture timestamp
- Case
- Entity
- Tags
- Analyst notes
- Actions for open source, download, copy link, export

## Report Preview Layout

Report preview should look like a document inside the app.

Include:

- Left report section navigation
- White report page preview
- Executive summary
- Scope and objective
- Methodology
- Findings
- Confidence summary
- Evidence table
- Timeline
- Recommendations
- Limitations

## Confidence Rules

Confidence must always use both color and text.

- High: green
- Medium: amber
- Low: slate gray
- Unknown: muted outline

Never rely on color alone.

## Copy Style

Use calm, evidence-based copy.

Good:

- “The domain appears recently registered.”
- “Confidence is medium because ownership could not be independently confirmed.”
- “This finding is based on limited public data.”
- “Review supporting evidence before drawing a conclusion.”

Avoid:

- “This is definitely malicious.”
- “Target acquired.”
- “Hunt this person.”
- “Exploit this lead.”
