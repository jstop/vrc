# Export Variants

## Context
The only export option is downloading the full VRC JSON blob. Users can't easily extract the defensible subset or share in standard argumentation formats.

## Proposed Exports
1. **Grounded-only VRC** — Just the claims in the grounded extension, with their relations
2. **Per-extension VRC** — One download per preferred extension
3. **Argdown format** — Markdown-like syntax used by the argumentation community
4. **Plain text summary** — Copy-pasteable narrative with claim texts and verdicts
5. **BibTeX citation** — For academic papers referencing a VRC analysis

## Implementation
- Add dropdown next to existing Download button
- Each format is a client-side transform of `currentVRC` — no backend changes
- Argdown spec: https://argdown.org/syntax/

## Effort
Medium — multiple export formats, each needs its own serializer
