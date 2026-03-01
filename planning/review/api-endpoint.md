# Structured API Endpoint

## Context
The current `/analysis/{id}` endpoint returns the full result blob. There's no way to query specific subsets (just grounded claims, just attacks, etc.) or get machine-friendly structured output.

## Proposed Endpoints
- `GET /api/analysis/{id}` — Full structured result
- `GET /api/analysis/{id}/grounded` — Just grounded extension claims with text
- `GET /api/analysis/{id}/preferred` — All preferred extensions
- `GET /api/analysis/{id}/attacks` — Attack relations with reasons
- `GET /api/analysis/{id}/status` — Argument status map

## Use Cases
- Downstream AI tools using grounded claims as verified context
- Research tools aggregating argumentation patterns
- Dashboard widgets showing analysis summaries
- CI/CD pipelines validating reasoning in documentation

## Effort
Small-medium — mostly reshaping existing data in new routes
