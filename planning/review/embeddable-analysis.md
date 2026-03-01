# Embeddable Analysis

## Context
Users can share permalinks but can't embed VRC analyses in external pages (blogs, papers, documentation).

## Design
- Add "Embed" button on permalink view
- Generates an iframe snippet: `<iframe src="https://vrc.routinebuilders.com/embed/{id}" ...>`
- `/embed/{id}` route serves a minimal page with just the graph + narrative (no header, no feed nav)
- Responsive, dark-themed, self-contained

## Implementation
- New Flask route `/embed/<analysis_id>` serving a stripped-down template
- Or reuse index.html with a `?embed=1` query param that hides chrome
- Copy-to-clipboard button for the embed code

## Effort
Medium — new route/template, responsive sizing, cross-origin considerations
