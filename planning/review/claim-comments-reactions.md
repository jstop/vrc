# Comments & Reactions per Claim

## Context
Analyses are read-only after creation. Users can't engage with specific claims — agree, disagree, add context, or challenge the extraction.

## Features
1. **Per-claim reactions** — Agree/Disagree buttons on each claim card
2. **Per-claim comments** — Threaded discussion on individual claims
3. **Analysis-level comments** — General discussion on the permalink

## Data Model
- New `reactions` table: `analysis_id, claim_id, handle, reaction_type`
- New `comments` table: `analysis_id, claim_id (nullable), handle, text, created_at`
- DynamoDB: nested items under analysis partition key

## Considerations
- Moderation needed for public comments
- Rate limiting on reactions
- Anonymous vs. handle-authenticated participation
- Could evolve into "fork analysis" — user adds counter-claims

## Effort
Large — new data model, moderation, real-time updates
