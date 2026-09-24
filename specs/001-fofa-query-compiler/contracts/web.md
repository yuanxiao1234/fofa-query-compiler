# Local Web Contract

## Runtime Boundary

- The service binds only to IPv4/IPv6 loopback in v1.
- Server-rendered HTML and local static assets are the user interface; no CDN is required.
- A high-entropy local session, SameSite/HttpOnly cookie, CSRF token, Host/Origin validation, bounded
  uploads, autoescaped templates, and safe workspace paths protect every write operation.
- HTTP handlers call shared application services and cannot render FOFA queries or bypass export gates.

## Pages

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/` | Current run overview, resume existing run, and import entry |
| GET | `/import` | Select three package inputs and show structural validation |
| GET | `/questions` | Filterable question queue and progress counters |
| GET | `/questions/{question_id}` | Intent, constraints, candidate, validation, risks, evidence, review |
| GET | `/evidence/{question_id}` | Evidence records and qualified replacement form |
| GET | `/export` | Preflight, complete blocker list, participant name, download action |
| GET | `/jobs/{job_id}` | Job details and polling fallback |
| GET | `/health` | Local liveness only; no sensitive details |

Question lists prioritize evidence-blocked, validation-failed, high-risk unconfirmed, ordinary
unconfirmed, then confirmed items. Navigation respects the current filter so a reviewer can process a
queue without silently skipping entries.

## Internal HTTP Interface

```text
POST   /api/v1/import
POST   /api/v1/generation-jobs
GET    /api/v1/jobs/{job_id}
GET    /api/v1/jobs/{job_id}/events
GET    /api/v1/status
GET    /api/v1/questions
GET    /api/v1/questions/{question_id}
PUT    /api/v1/questions/{question_id}/answer
POST   /api/v1/questions/{question_id}/validate
POST   /api/v1/questions/{question_id}/confirm
DELETE /api/v1/questions/{question_id}/confirmation
POST   /api/v1/questions/{question_id}/evidence
PUT    /api/v1/questions/{question_id}/evidence/{evidence_id}
POST   /api/v1/export
GET    /api/v1/exports/{export_id}/download
```

Mutable question requests carry `expected_revision`; stale revisions return `409 Conflict`. The server
re-evaluates validation, evidence, risk, and confirmation requirements for every confirm and export
request and never trusts browser booleans.

## Error Body

```json
{
  "error": {
    "code": "EVIDENCE_REQUIRED",
    "message": "该题缺少可核验来源，暂不能确认",
    "question_id": "M096-S001",
    "details": [],
    "request_id": "local-example"
  }
}
```

Use `400` for malformed values, `404` for unknown resources, `409` for revision/job/state conflicts,
`422` for domain validation failures, `423` for evidence or workflow locks, and `500` for safe internal
errors. Responses never expose secrets, stack traces, or unrestricted absolute paths.

## Background Jobs and SSE

Imports are synchronous. Generation and full validation use an in-process controlled job; one active
write job is permitted per run. Job states are `queued`, `running`, `completed`,
`completed_with_errors`, `failed`, `cancelled`, and `interrupted`.

`GET /api/v1/jobs/{job_id}/events` emits sequenced SSE events:

```text
job.started
question.started
question.generated
question.blocked
question.failed
progress.updated
job.completed
```

Each event carries job ID, monotonic sequence, timestamp, processed/total counts, optional question ID,
status, and a safe message. Reconnect resumes after the last sequence; the job endpoint remains the
source of final truth. Closing or refreshing the page does not cancel work. An interrupted process keeps
completed items and marks the job interrupted for safe resumption.

## Review and Export Gates

- Ordinary questions require current validation and explicit “all atomic constraints checked” consent.
- High-risk questions additionally require every risk item and required evidence record to be checked.
- Fixed rejection requires a deterministic reason; source access failure is not a valid rejection.
- Editing an answer or relevant evidence creates a new revision and invalidates confirmation.
- The export page runs a read-only preflight and lists every blocker. The server runs preflight again on
  submit. There is no force export.
- A successful export creates an immutable artifact and returns its ID, SHA-256, time, and download URL.
  Browser-side code never assembles the competition JSON.
