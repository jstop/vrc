# Re-analyze with Delta Reporting

## Context
Depends on the versioned analysis architecture (see `versioned-analysis-architecture.md`). When users re-analyze the same text, they should see what changed.

## Design
After `/reanalyze` creates a new record:
- Show a delta view: old analysis vs new analysis
- Highlight: new claims found, removed claims, changed relations, flipped statuses
- Side-by-side or inline diff of claim lists

## Data Available
- Old `result_json` from the original analysis
- New `result_json` from re-analysis
- Claim IDs may differ between runs (Claude non-determinism)

## Challenges
- Claim IDs are arbitrary (c1, c2...) — need semantic matching to align claims across runs
- Could use text similarity (fuzzy match) to pair old/new claims
- Or just show both side-by-side without alignment

## Effort
Medium-large — semantic claim matching is the hard part
