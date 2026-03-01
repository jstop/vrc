# Versioned Analysis Architecture

## Context

As VRC evolves, the extraction prompt, solver, and views change independently. Old analyses lack newer fields (e.g., `topic`). The user wants each analysis version to own its renderer so versions coexist without backward-compat hacks, and users can re-analyze old content with the current version.

## Core Design

A single **`schema_v`** integer stamps each analysis. It bumps whenever the combined output shape changes (extraction prompt or solver). The frontend has a renderer registry keyed by this version. Old renderers freeze in place when new versions arrive.

**Pragmatic phasing:** Today's renderers handle old data fine via `|| []` fallbacks. We build the scaffold (stamp + registry + dispatch), register the current code as **v1** (which also serves as v0 fallback), and defer renderer duplication until a v2 with genuinely incompatible data arrives.

---

## Files to Modify

| File | Changes |
|------|---------|
| `app.py` | `SCHEMA_VERSION` constant, `_meta` in result blob, `_summary_fields()` helper, source_preview in feed, `/reanalyze` endpoint |
| `templates/index.html` | Renderer registry + dispatch, version banner with re-analyze button, feed card source_preview fallback |

---

## 1. Backend (`app.py`)

### 1a. Version Stamp

```python
SCHEMA_VERSION = 1  # bump when extraction prompt or solver output shape changes
```

Embed in every new analysis:

```python
result = {
    "_meta": {"schema_v": SCHEMA_VERSION},
    "claims": ..., "attacks": ..., "supports": ...,
    "analysis": ..., "vrc": ...,
}
```

Records without `_meta` are implicitly v0. No migration needed.

### 1b. `_summary_fields()` Helper

Extract the inline denormalization (topic, summary_label, counts) into one function. Used by both `/analyze` and `/reanalyze`. Eliminates the current pattern of computing summary values inline in two places.

### 1c. Source Preview in Feed

For old analyses without `topic`, feed cards need identifying text.

- **SQLite**: `substr(source_text, 1, 120) as source_preview` in feed query
- **DynamoDB**: Store `source_preview` at write time. Old items lack it — frontend falls back to `summary_label`

### 1d. `/reanalyze/<analysis_id>` Endpoint

```
POST /reanalyze/<analysis_id>
Response: same shape as /analyze, with new id
```

1. Load existing record's `source_text` and `handle`
2. Re-run full pipeline (extract → solve → VRC) with current code
3. Stamp `_meta` with current `SCHEMA_VERSION`
4. Save as **new record** — old permalink stays valid
5. Return new ID

### 1e. VRC Credential Versioning

Add `"version": {"schema": SCHEMA_VERSION}` to `credentialSubject` in `build_vrc()` so downloaded VRC JSON is self-describing.

---

## 2. Frontend (`templates/index.html`)

### 2a. Renderer Registry

```javascript
var SCHEMA_V = {{ schema_version }};  // injected by Flask

var RENDERERS = {
    claims:    { 1: renderClaims },
    narrative: { 1: renderNarrative },
    graph:     { 1: renderGraph },
    stats:     { 1: renderStats },
};

function getRenderer(kind, data) {
    var v = (data._meta && data._meta.schema_v) || 0;
    var versions = RENDERERS[kind] || {};
    return versions[v] || versions[1];  // fall back to v1 for unknown/old versions
}
```

All call sites change from `renderClaims(data, panelId)` to `getRenderer('claims', data)(data, panelId)`. This is the scaffold — when v2 arrives, you add `{ 2: renderClaims_v2 }` and freeze the v1 function.

### 2b. Version Banner

On permalink view, if `schema_v < SCHEMA_V`:

```
Analyzed with an earlier version of VRC.  [Re-analyze →]
```

Styled as a subtle bar above the narrative panel. Clicking calls `POST /reanalyze/<id>` and navigates to the new permalink.

### 2c. Feed Card Title Fallback

```javascript
var title = item.topic || item.source_preview || item.summary_label || 'Analysis';
```

---

## What Happens When v2 Arrives (Future)

1. Change `EXTRACTION_PROMPT` (e.g., add per-claim confidence scores)
2. Set `SCHEMA_VERSION = 2`
3. **Freeze** `renderClaims` as `renderClaims_v1` (rename, never modify again)
4. Write `renderClaims_v2` that expects the new fields
5. Update registry: `claims: { 1: renderClaims_v1, 2: renderClaims_v2 }`
6. All old analyses auto-render with v1, show upgrade banner
7. Users re-analyze at their own pace

Only the renderers that *actually differ* need version splits. If `renderGraph` is unchanged between v1 and v2, it stays shared.

---

## Implementation Order

1. `_summary_fields()` helper — refactor, no behavior change
2. `_meta` stamping — add constant, embed in result blob + VRC credential
3. Source preview — SQLite substr, DynamoDB attribute, feed card fallback title
4. Renderer registry + dispatch — scaffold with current renderers as v1
5. `/reanalyze` endpoint + version banner — upgrade flow

## Verification

1. `pytest tests/` — existing tests pass
2. New analysis → `_meta.schema_v: 1` in response
3. Old permalink → renders fine (v1 fallback), shows version banner
4. Click "Re-analyze" → new record at v1, navigates to new permalink
5. Feed → old analyses show source preview or summary_label, new ones show topic
6. Download VRC → `version.schema` in credential
