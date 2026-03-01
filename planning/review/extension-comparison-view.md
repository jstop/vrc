# Extension Comparison View

## Context
When multiple preferred extensions exist (genuine disagreement), the narrative just says "N incompatible worldviews" with claim chips. Users can't see *where* the worldviews diverge without manually cross-referencing.

## Design
Side-by-side table in the narrative panel, shown only when `preferred_extensions.length > 1`:
- Rows: each claim
- Columns: each preferred extension (worldview)
- Cells: checkmark (included) or dash (excluded), color-coded
- Highlight rows where extensions diverge (the interesting claims)

## Data Available
- `data.analysis.preferred_extensions` — array of arrays of claim IDs
- `data.claims` — full claim text for each ID
- Already computed, no backend changes needed

## Implementation
- New function `renderExtensionComparison(data, panelId)`
- Inserted into narrative panel when preferred extensions > 1
- CSS: table with sticky header, alternating rows, divergence highlighting
- ~60-80 lines of JS + ~20 lines of CSS

## Effort
Small — purely frontend, data already available
