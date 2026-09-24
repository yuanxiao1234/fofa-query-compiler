# Phase 0 Research: FOFA Natural-Language Query Compiler

## Decision 1: Modular Python monolith with shared application services

**Decision**: Use Python 3.12+ in one installable package. Domain and application services own all
translation, validation, evidence, review, and export behavior. The CLI and local Web UI are adapters
over those services.

**Rationale**: The workload is one local user and 100 questions. A single process keeps state,
reproducibility, and testing tractable while ensuring Web and CLI cannot implement divergent rules.

**Alternatives considered**:

- Separate frontend/backend services: rejected because they add deployment and contract overhead.
- Agent/workflow framework: rejected because implicit state and upgrade churn weaken determinism.
- One script or notebook: rejected because it cannot enforce typed boundaries and review state safely.

## Decision 2: Local Web UI with FastAPI, Jinja2, and HTMX

**Decision**: Deliver the first Web UI using FastAPI, Jinja2, locally vendored HTMX, small local CSS,
and only the JavaScript needed for SSE and minor interaction. Uvicorn binds to `127.0.0.1` by default.
No Node build, public deployment, login system, or multi-user mode is included.

**Rationale**: Server-rendered pages can deliver import, progress, filtering, review, evidence, and
download quickly. FastAPI shares Pydantic contracts with the core and provides simple SSE endpoints.
The user's urgent UI need is documented while the system stays a local modular monolith.

**Alternatives considered**:

- React or Vue SPA: rejected due to a second build, duplicated types, and excess state complexity.
- Streamlit or Gradio: rejected because strict revisions, state transitions, and export gates are hard
  to represent and contract-test cleanly.
- Django: rejected because its ORM, accounts, and administration surface exceed the v1 need.
- Electron: rejected because packaging a desktop runtime is unnecessary for a localhost tool.

## Decision 3: Pydantic at boundaries, plain services for behavior

**Decision**: Pydantic v2 models define imported files, normalized intent, discriminated AST nodes,
validation reports, evidence, risk, review, run manifests, HTTP payloads, and exports. Strict validation
and forbidden unknown fields are used at boundaries. Compilation behavior stays in ordinary services.

**Rationale**: Pydantic gives precise input errors, tagged unions, and JSON Schema without hiding
business operations inside validators.

**Alternatives considered**:

- Dynamic dictionaries: rejected because illegal field/operator/value combinations remain possible.
- Dataclasses plus manual validation: rejected because nested input errors and schema generation are
  materially weaker.
- Business logic in model validators: rejected because ordering and side effects become implicit.

## Decision 4: Separate normalized intent from FOFA AST

**Decision**: Parse each question into a `NormalizedIntent` containing all atomic semantic constraints.
Compile only representable constraints into a discriminated `QueryAST` of predicate and Boolean nodes.
A `RejectionDecision` is a separate type, never an AST node or empty string.

**Rationale**: Comparing intent constraints with AST coverage detects syntactically valid queries that
silently omit a restriction. It also separates “not understood,” “not representable,” and “evidence
temporarily unavailable.”

**Alternatives considered**:

- Generate query strings directly: rejected due to grouping, escaping, and audit risks.
- Use a flat predicate list: rejected because nested AND/OR/NOT cannot be represented faithfully.
- Put source intent and FOFA representation in one model: rejected because platform limits would hide
  normalization omissions.

## Decision 5: Rule-first translation with a narrow optional LLM adapter

**Decision**: Versioned deterministic rules translate unambiguous families. A provider-neutral adapter
may propose schema-constrained IR for complex language, but it cannot return final FOFA text. All model
output passes strict schema, registry, semantic coverage, evidence, and logic validation. Tests use a
fake or recorded adapter and do not require a network.

**Rationale**: Rules handle the many IP, CIDR, port, ASN, geography, domain, and protocol cases
reliably; a constrained model remains useful for complex language without controlling syntax.

**Alternatives considered**:

- Full LLM query generation: rejected as non-deterministic and difficult to audit.
- Pure rules for every phrase: rejected because language variants and cross-engine migration would
  become brittle.
- Direct dependency on one provider SDK: rejected because it couples the core and breaks offline tests.

## Decision 6: Versioned supported FOFA subset and explicit parser boundary

**Decision**: Implement only the fields, operators, value types, and match modes backed by verified
evidence and required by the current intent catalog. A field registry defines legal combinations. The
renderer owns all grouping, quoting, and escaping. A small lexer/recursive-descent parser validates
rendered and manually edited queries. Lark is not a required dependency in v1; introduce it only when
tests prove the supported grammar exceeds a maintainable hand-written parser.

**Rationale**: The generated path already owns the AST. Claiming full FOFA grammar support without a
complete authoritative grammar would create false confidence. Manual edits still require reparsing.

**Alternatives considered**:

- Lark immediately: deferred until there is a verified grammar and demonstrated need.
- Regex-only parsing: rejected because nested grouping and escaped strings are recursive.
- Accept arbitrary query strings: rejected because unknown fields and operators could bypass evidence.

## Decision 7: Versioned JSON/JSONL workspace instead of a database

**Decision**: Each run is a local directory containing a manifest, normalized package, per-question
state, evidence, immutable candidate revisions, validation/review records, append-only audit events,
jobs, and isolated exports. Writes use a temporary file plus atomic replacement. A per-run lock and
expected revision prevent concurrent overwrites.

**Rationale**: At 100 items and one user, files are inspectable, portable, recoverable, and shared by
CLI and Web. They expose state for audit without database migrations.

**Alternatives considered**:

- SQLite: deferred until multi-user concurrency or large historical querying is required.
- One large mutable JSON file: rejected because a single write can damage all state and creates noisy
  revisions.
- Browser-only or in-memory state: rejected because refresh or restart would lose review progress.

## Decision 8: Orthogonal workflow states and immutable finalization

**Decision**: Store generation, validation, evidence, review, and finalization states independently,
then derive a display status. Any candidate, rule, or relevant evidence change makes dependent
validation, confirmation, and finalization stale. A final answer is an immutable projection of a
specific validated and confirmed candidate revision.

**Rationale**: “Validated but evidence-blocked” and “confirmed before a later edit” cannot be expressed
safely by a single linear status. Orthogonal states make export gates precise.

**Alternatives considered**:

- One giant status enum: rejected due to combinatorial growth and ambiguous transitions.
- Editable final answers: rejected because verification and confirmation would refer to old content.
- Evidence failure as rejection: rejected because access failure is not a FOFA capability decision.

## Decision 9: Background jobs with SSE progress

**Decision**: Imports are synchronous; batch generation and validation run as controlled in-process
jobs. One run permits one active write job. Progress is persisted as sequenced events and streamed to
the browser with SSE, with a normal status endpoint as reconnect and polling fallback.

**Rationale**: SSE matches one-way progress and is simpler than WebSocket. A broker and separate worker
are unnecessary. Persisted events let page refreshes and process interruptions show truthful state.

**Alternatives considered**:

- One long HTTP request: rejected due to timeout and lost progress on refresh.
- Polling only: retained as fallback but not primary due to latency and request noise.
- Celery/Redis: rejected because it adds deployment infrastructure to a local single-user tool.

## Decision 10: All-or-nothing semantic acceptance and layered tests

**Decision**: A benchmark item passes only when every applicable atomic constraint is correct. Two
independent benchmark judgements are reconciled before scoring. Test layers cover schemas, property
boundaries, AST/render/parse, registry contracts, intent-family fixtures, application workflows, CLI,
HTTP/pages/SSE, a minimal browser journey, the current 100-item package, reproducibility, and secret
scanning.

**Rationale**: Exact query strings can differ while semantics match; partial scores can hide a missing
restriction. Layering gives fast defect localization while retaining full-package proof.

**Alternatives considered**:

- Golden string snapshots only: rejected because they misclassify equivalent queries and hide meaning.
- Live FOFA result comparison as the main gate: rejected because it requires credentials and results
  vary with the index.
- Browser E2E only: rejected because it is slow and cannot isolate compiler correctness.

## Decision 11: Local Web security remains mandatory

**Decision**: Reject non-loopback binding in v1; use a high-entropy local session, SameSite/HttpOnly
cookie, CSRF token, Host/Origin validation, no CORS, bounded uploads, safe generated paths, autoescaped
templates, locally served assets, and secret-redacted errors/logs. Browser requests cannot select paths
outside the configured workspace root.

**Rationale**: A malicious website can still target localhost. The Web UI controls files, confirmations,
and exports, so local-only does not eliminate request-forgery and path risks.

**Alternatives considered**:

- No browser protections on localhost: rejected as unsafe.
- Full user authentication: rejected as unnecessary for a single-user loopback service.
- Listen on `0.0.0.0`: rejected because it creates an unauthorized remote surface.

## Resolved Unknowns

- Web UI is required in v1 and does not replace the CLI.
- No database, queue broker, Node frontend, deployment target, or account system is required.
- Lark is deferred behind an evidence-based trigger, not assumed.
- External evidence unavailability is a blocking state with qualified alternative sources.
- Benchmark double review and formal-answer single-user confirmation are distinct workflows.
- Phase 1 design has no unresolved clarification markers.
