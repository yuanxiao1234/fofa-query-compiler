# Workspace and File Contract

## Directory Layout

```text
<workspace-root>/<run-id>/
├── manifest.json
├── package.json
├── questions.json
├── state.json
├── items/
│   └── <question-id>/
│       ├── intent.json
│       ├── candidates/
│       ├── validations/
│       ├── risks.json
│       ├── reviews/
│       └── final-answer.json
├── evidence/
│   └── <question-id>/
├── jobs/
├── audit/
│   └── events.jsonl
└── exports/
    ├── <export-id>.metadata.json
    └── <export-id>-answer.json
```

Paths are generated from validated identifiers. Browser filenames never become storage paths. Original
source files remain read-only and are represented by digests in `manifest.json`.

## Manifest Contract

The manifest records schema version, package ID, original question order, source SHA-256 values, code
version, Python and dependency lock fingerprints, rule/registry/vocabulary fingerprints, validator and
renderer versions, adapter/provider/model/prompt/schema identifiers, and evidence-set fingerprints.
Credentials and implicit reasoning are forbidden.

## Mutation Contract

- Files are UTF-8 JSON or JSONL.
- Mutable pointers are updated using a temporary sibling file, flush, and atomic replacement.
- Candidate, validation, evidence verification, review, and export records are immutable revisions.
- Audit events append structured action and result metadata without secrets or model reasoning traces.
- A run-scoped lock serializes writes; expected revisions detect stale Web tabs and CLI/Web races.
- Relevant source, rule, evidence, adapter configuration, or candidate changes invalidate downstream
  validation, review, finalization, and export readiness.

## Competition Input Contract

Question input is a JSON array of unique `{题号, 自然语言输入}` objects. Package information contains a
non-empty package identifier and optional RFC 3339 issue time. The answer template contains participant
name, the exact package identifier, and unique `{题号, 查询语句}` entries. Question and template ID sets
must be equal; question order is authoritative for export.

## Answer Export Contract

The only submission-shaped artifact is UTF-8 JSON below 8 MB:

```json
{
  "选手名称": "实际选手名称",
  "参赛包编号": "pkg-08e82c8d",
  "答案": [
    {
      "题号": "M001-S009",
      "查询语句": "ip=\"20.247.40.92\""
    }
  ]
}
```

Every source question appears exactly once and in source order. A query is either one confirmed FOFA
query or the exact fixed rejection text. No explanation, Markdown, candidate, AST, evidence, audit,
credential, or internal state is allowed. Export preflight completes before creating or replacing an
artifact; failure cannot leave a partial file.

## Supported Query Contract Boundary

The field registry is the authority for the versioned FOFA subset. For every field it stores value type,
allowed operators, match semantics, regex support, quoting behavior, and evidence metadata. Unknown or
unverified combinations fail closed. Parser success proves only structure; semantic coverage compares
every required atomic intent constraint with AST nodes or a verified rejection reason.
