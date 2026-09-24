# Data Model: FOFA Natural-Language Query Compiler

## Modeling Rules

- Persisted models carry `schema_version` and reject unknown fields.
- IDs are stable opaque strings; question IDs preserve the source text exactly.
- Candidate, validation, evidence, review, and export changes create revisions or immutable records.
- Timestamps use timezone-aware ISO 8601 values; content fingerprints use SHA-256.
- Secret values and model reasoning traces are never persisted.
- The submitted answer sheet is a projection, not a serialization of internal models.

## Aggregate: CompetitionPackage

Represents one imported competition package and is the root for completeness checks.

| Field | Type | Rules |
|-------|------|-------|
| `run_id` | string | Generated locally; unique within the workspace root |
| `package_id` | string | Non-empty; copied without normalization |
| `issued_at` | datetime/null | Timezone-aware when present |
| `participant_name` | string/null | Required and non-empty only for export |
| `source_manifest` | `SourceManifest` | Paths, media type, size, and digest for every source |
| `questions` | list of `Question` | Non-empty; question IDs unique |
| `template_question_ids` | list of string | Set must equal question IDs |
| `original_order` | list of string | Contains every question ID exactly once |
| `rules_fingerprint` | string | Identifies registry, rules, and vocabularies |
| `import_report` | `ValidationReport` | Must pass before generation |
| `created_at` | datetime | Immutable |

Package-derived states are `INVALID_IMPORT`, `IN_PROGRESS`, `BLOCKED`, `READY_FOR_EXPORT`, and
`EXPORTED`. Only all finalized questions plus a passing preflight yield `READY_FOR_EXPORT`.

## Entity: Question

| Field | Type | Rules |
|-------|------|-------|
| `question_id` | string | Unique inside package; recommended `^M\d{3}-S\d{3}$` |
| `ordinal` | integer | Zero-based source order; unique inside package |
| `raw_text` | string | Non-empty and immutable |
| `source_location` | string | Diagnostic locator, not a browser-controlled path |
| `fingerprint` | string | Hash of ID and original text |
| `intent_family` | string/null | Versioned classifier output |
| `requires_external_evidence` | boolean | Derived, then reviewable |

A question has many candidate revisions, evidence records, validation reports, and review records, but
at most one current candidate and one current final answer.

## Entity: NormalizedIntent

Describes what the question means independently of FOFA syntax.

| Field | Type | Rules |
|-------|------|-------|
| `question_id` | string | References one question |
| `intent_version` | string | Identifies normalizer and schema |
| `atomic_constraints` | list of `AtomicConstraint` | Non-empty for understood requests |
| `required_semantics` | list of string | Human-readable completeness checklist |
| `external_facts` | list of `EvidenceFactRef` | Required facts must resolve before confirmation |
| `convertibility` | enum | `unknown`, `convertible`, `not_convertible`, `blocked_evidence` |
| `warnings` | list of finding | Never silently discarded |

### AtomicConstraint

| Field | Type | Rules |
|-------|------|-------|
| `constraint_id` | string | Unique within intent |
| `semantic_role` | enum | Field, scope, match, boundary, grouping, negation, existence, count |
| `target_concept` | string | Domain concept before FOFA field mapping |
| `match_mode` | enum/null | Exact, contains, regex, exists, comparison, range |
| `typed_value` | tagged value/null | Preserves type and source spelling |
| `polarity` | enum | Positive or negative |
| `group_path` | list of string | Captures nested Boolean relationship |
| `boundary_semantics` | object/null | Inclusive/exclusive and lower/upper boundary |
| `must_preserve` | boolean | Required constraints are all-or-nothing |
| `evidence_refs` | list of string | Links facts or field evidence |

## Entity: QueryAST

A discriminated union representing only the supported FOFA subset.

- `Predicate(field, operator, value, match_mode, constraint_refs, evidence_refs)`
- `And(children)` with at least two children
- `Or(children)` with at least two children
- `Not(child)` only where registry semantics permit it

Typed values include text, integer, boolean, timestamp, IPv4, IPv6, CIDR, IP closed range, hash,
certificate serial, and regex. Every leaf maps to one or more atomic constraints. The renderer consumes
only validated AST nodes and is the sole producer of query text.

## Entity: CandidateAnswer

Immutable revision with exactly one payload kind.

| Field | Type | Rules |
|-------|------|-------|
| `candidate_id` | string | Stable across its immutable record |
| `question_id` | string | References one question |
| `revision` | positive integer | Strictly increases per question |
| `created_by` | enum | `rule`, `llm_adapter`, `reviewer` |
| `input_fingerprint` | string | Binds question, rules, facts, and adapter configuration |
| `created_at` | datetime | Immutable |
| `payload` | tagged union | `QueryCandidate` or `RejectionCandidate`, never both |

`QueryCandidate` holds the intent, AST, and rendered query. `RejectionCandidate` holds the exact fixed
text, a deterministic reason code, unsupported constraints, and supporting evidence. Evidence access
failure is not a valid rejection reason.

## Entity: ValidationReport

Immutable result bound to one candidate revision.

| Field | Type | Rules |
|-------|------|-------|
| `report_id` | string | Unique |
| `candidate_id` / `revision` | reference | Must match the validated revision |
| `input_checks` | list of finding | Package and input checks |
| `syntax_checks` | list of finding | Grammar, grouping, quoting, escaping |
| `type_checks` | list of finding | Field/operator/value and range checks |
| `coverage_checks` | list of finding | Every required constraint maps to AST/rejection reason |
| `logic_checks` | list of finding | Contradiction and unsafe broadening checks |
| `validator_version` | string | Revalidation trigger when changed |
| `is_valid` | boolean | False if any blocking finding exists |
| `validated_at` | datetime | Immutable |

Each finding carries code, severity, data path, message, related constraints, and `blocking`. Candidate
changes immediately make the prior report stale.

## Entity: EvidenceRecord

| Field | Type | Rules |
|-------|------|-------|
| `evidence_id` | string | Unique within run |
| `question_id` | string | References one question |
| `source_kind` | enum | `official_primary`, `official_alternative`, `verified_archive`, `user_provided`, `project_rule_reference` |
| `source_locator` | string | URL or safe local material identifier |
| `original_source_locator` | string/null | Required for alternative sources |
| `retrieved_at` | datetime/null | Required when content was accessed |
| `content_digest` | string/null | Required for sufficient evidence |
| `access_status` | enum | `accessible`, `unavailable`, `changed`, `invalid` |
| `extracted_facts` | list of `EvidenceFact` | Non-empty for sufficient evidence |
| `equivalence_assessment` | object/null | Required for alternative/archive evidence |
| `verified_by` / `verified_at` | string/datetime/null | Required before becoming sufficient |
| `is_sufficient` | boolean | Computed from source qualification and verification |

An unavailable primary record may coexist with a qualified alternative. A URL alone, a search snippet,
or model memory cannot become sufficient evidence.

## Entity: RiskAssessment

| Field | Type | Rules |
|-------|------|-------|
| `risk_level` | enum | `low`, `medium`, `high` |
| `risk_items` | list of `RiskItem` | Structured, never only a label |
| `requires_manual_confirmation` | boolean | Always true in v1 |
| `requires_evidence_review` | boolean | Derived from risk items |
| `assessment_version` | string | Reassessment trigger |

Risk codes cover nested logic, regex, escaping, external evidence, fingerprint derivation, syntax
migration, certificate/TLS fields, boundaries, safe rejection, low confidence, and incomplete automatic
proof. Each risk item has a checklist, resolution state, resolver, time, and notes.

## Entity: ReviewRecord

Formal-answer confirmation of one exact candidate and validation report.

| Field | Type | Rules |
|-------|------|-------|
| `review_id` | string | Unique |
| `question_id` | string | References one question |
| `candidate_revision` | integer | Must be current |
| `validation_report_id` | string | Must be passing and current |
| `reviewer` | string | Non-empty local reviewer label |
| `decision` | enum | `confirmed`, `revised`, `returned` |
| `reviewed_evidence_ids` | list of string | Must satisfy required facts |
| `checked_risk_item_ids` | list of string | All required high-risk items present |
| `revision_note` | string/null | Required for reviewer edits |
| `confirmed_at` | datetime/null | Present only for confirmation |

Editing a candidate or relevant evidence makes existing confirmation stale. Benchmark review uses
separate `BenchmarkJudgement` and `AdjudicationRecord` entities because its two-reviewer rule is not the
same as formal-answer confirmation.

## Entity: FinalAnswer

Immutable projection created only when the current candidate is valid, evidence is sufficient, the
human confirmation targets the current revision, and high-risk checks are complete.

Fields: `question_id`, `candidate_revision`, `answer_kind`, `query_text`, `validation_report_id`,
`review_record_id`, `finalized_at`, and `finalization_fingerprint`. Any dependency change makes it stale.

## Entity: AnswerSheet and ExportArtifact

`AnswerSheet` contains only:

- `选手名称`
- `参赛包编号`
- `答案`: ordered objects containing `题号` and `查询语句`

`ExportArtifact` stores internal metadata separately: export ID, answer-sheet digest, byte size,
creation time, preflight report, and safe local file location. No internal metadata enters the answer.

## Entity: GenerationJob

| Field | Type | Rules |
|-------|------|-------|
| `job_id` | string | Unique within run |
| `run_id` | string | One active write job per run |
| `kind` | enum | `generate`, `validate_all` |
| `status` | enum | `queued`, `running`, `completed`, `completed_with_errors`, `failed`, `cancelled`, `interrupted` |
| `processed` / `total` | integer | `0 <= processed <= total` |
| `counts` | object | Converted, refused, failed, blocked, review-required |
| `last_sequence` | integer | Monotonic event position |
| `started_at` / `finished_at` | datetime/null | State-dependent |

Events have job ID, sequence, timestamp, event type, optional question ID, counts, status, and safe
message. Browser disconnect does not change the job.

## Orthogonal Question States

- Generation: `not_started`, `candidate_ready`, `generation_failed`
- Validation: `not_run`, `passed`, `failed`, `stale`
- Evidence: `not_required`, `pending`, `sufficient`, `blocked`
- Review: `not_reviewed`, `changes_requested`, `confirmed`, `stale`
- Finalization: `not_finalized`, `finalized`, `stale`

Derived display states are `IMPORTED`, `CANDIDATE_READY`, `VALIDATION_FAILED`, `BLOCKED_EVIDENCE`,
`AWAITING_REVIEW`, `REVIEW_CHANGES_REQUIRED`, `READY_TO_FINALIZE`, and `FINALIZED`.

## State Transitions

1. Valid import creates `IMPORTED` questions.
2. Candidate creation sets `CANDIDATE_READY` and stales prior dependent records.
3. Failed validation yields `VALIDATION_FAILED`.
4. Missing required facts yields `BLOCKED_EVIDENCE`, even if syntax passes.
5. Passing validation plus sufficient evidence yields `AWAITING_REVIEW`.
6. Reviewer edits create a new candidate revision and return to validation.
7. Reviewer confirmation requires a current passing report; high-risk items additionally require all
   risk and evidence checks.
8. Valid confirmation yields `READY_TO_FINALIZE`; finalization creates an immutable `FinalAnswer`.
9. Any affected input, rule, candidate, validator, or evidence change stales downstream state.
10. Only all `FINALIZED` questions plus package preflight allow `READY_FOR_EXPORT`.

## Cross-Entity Invariants

1. Package and template question-ID sets are equal, unique, and complete.
2. Original package ID, question text, IDs, and order are immutable.
3. Every candidate is exactly one query or exact fixed rejection.
4. Every required atomic constraint maps to an AST node or verified rejection reason.
5. Validation and confirmation bind to exact revisions and cannot survive relevant edits.
6. All questions require human confirmation; high-risk questions require completed risk/evidence checks.
7. Evidence unavailability blocks and never automatically rejects.
8. Only qualified and verified alternative evidence can replace an inaccessible primary source.
9. Export is all-or-nothing, ordered, complete, valid UTF-8 JSON, and contains no internal data.
10. CLI and Web use the same records and services and must create equivalent export bytes.
