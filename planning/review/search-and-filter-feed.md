# Search & Filter on Feed

## Context
The feed is a flat chronological list. As analyses accumulate, users can't find specific topics, handles, or verdict types.

## Features
1. **Text search** — Search by topic, claim text, or handle
2. **Verdict filter** — Show only: Fully Coherent, Contested, Unresolved, Mixed
3. **Handle filter** — Show analyses from a specific user
4. **Sort options** — By date, by claim count, by acceptance ratio

## Backend Changes
- SQLite: Add LIKE queries on `topic`, `summary_label`, `handle`
- DynamoDB: More complex — may need GSI on topic or full-text search via OpenSearch
- Query params on `/feed`: `?q=search&verdict=contested&handle=alice`

## Frontend Changes
- Filter bar above feed cards
- Search input + dropdown filters
- Update `loadFeed()` to pass query params

## Effort
Medium — backend query changes needed, DynamoDB search is non-trivial
