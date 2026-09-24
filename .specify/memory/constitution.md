<!--
Sync Impact Report
- Version change: template (unratified) -> 1.0.0
- Modified principles:
  - Placeholder Principle 1 -> I. Accuracy and Source Fidelity
  - Placeholder Principle 2 -> II. Typed Intermediate Representation
  - Placeholder Principle 3 -> III. Deterministic Validation and Safe Rejection
  - Placeholder Principle 4 -> IV. Evidence-Based Evaluation
  - Placeholder Principle 5 -> V. Reproducible and Auditable Output
- Added sections:
  - Technology and Architecture Constraints
  - Development Workflow and Quality Gates
- Removed sections: none
- Follow-up TODOs: none
-->
# FOFA Natural-Language Query Compiler Constitution

## Core Principles

### I. Accuracy and Source Fidelity
Every generated query MUST preserve the user's complete search intent, including field semantics,
operator precedence, exact versus fuzzy matching, negation, geographic scope, time boundaries, and
literal escaping. FOFA field names, operators, value formats, and platform-specific capabilities MUST
be grounded in verified FOFA syntax or project-maintained evidence. External-document questions MUST
use the referenced source rather than model memory. When authoritative evidence conflicts with a
heuristic or model suggestion, the authoritative evidence wins.

Rationale: scoring is based on the query's actual result, so a plausible-looking query is not enough.

### II. Typed Intermediate Representation
Natural language MUST first be converted into a typed intermediate representation (IR), then rendered
into FOFA syntax. The IR MUST represent predicates, AND/OR/NOT groups, parentheses, comparison modes,
value types, and source evidence. Query strings MUST NOT be assembled by unconstrained concatenation.
LLMs MAY propose an IR or classify intent, but deterministic code MUST normalize and render the final
query. Reusable mappings such as countries, protocols, products, and cloud providers MUST live in
versioned data rather than duplicated prompt prose.

Rationale: a typed IR makes precedence, escaping, validation, and testing explicit and reviewable.

### III. Deterministic Validation and Safe Rejection
Every candidate answer MUST pass deterministic validation before export. Validation MUST cover legal
fields and operators, balanced grouping and quoting, type/range rules for IP addresses, CIDRs, ports,
ASNs, timestamps, hashes, and mutually contradictory predicates. Requests that cannot be represented
faithfully as a FOFA query MUST produce exactly `该需求不能直接转换为FOFA搜索语句`; the system MUST
NOT invent unsupported fields, runtime telemetry, subjective criteria, or unavailable facts. A
low-confidence model result MUST be routed for evidence review or safe rejection, never silently
accepted.

Rationale: a correct refusal scores better than a fabricated or syntactically invalid query.

### IV. Evidence-Based Evaluation
Each supported intent family MUST have independent fixtures derived from its own source example and
expected semantics. Tests MUST include positive cases, negative cases, precedence-sensitive cases,
escaping cases, invalid input, and known non-convertible requests. Golden outputs are allowed only
when manually reviewed; broad snapshots MUST NOT replace semantic assertions. For a formal answer
package, all 100 items MUST receive individual validation, and complex or externally sourced items
MUST receive individual evidence review.

Rationale: aggregate success can hide a single missing, duplicated, or semantically inverted answer.

### V. Reproducible and Auditable Output
Given identical input, rule data, model configuration, and evidence, the pipeline MUST produce the
same normalized answer file. Each item MUST retain an audit record containing its normalized intent,
IR, validation outcome, confidence/review status, and evidence references, while the submitted JSON
MUST contain only the required schema and final query. Secrets, FOFA credentials, private datasets,
and reasoning traces MUST NOT enter submitted artifacts or source control.

Rationale: reproducibility enables debugging and auditing without contaminating the competition file.

## Technology and Architecture Constraints

- The reference implementation MUST use Python 3.12 or newer for its strong text-processing,
  validation, testing, and LLM-integration ecosystem.
- Pydantic v2 MUST define input, IR, validation-result, audit-record, and answer-file schemas.
- A small explicit AST renderer and parser/validator MUST own FOFA syntax generation. Lark MAY be used
  for grammar parsing if the grammar becomes non-trivial; dependencies MUST be justified by tests.
- Provider-specific LLM access MUST sit behind a narrow adapter. Rules, validation, and exports MUST
  remain runnable without a live model so test results do not depend on network availability.
- Pytest MUST provide unit, property-oriented boundary, golden-fixture, and end-to-end package tests.
- The first product surface MUST be a local CLI. A web UI, database, distributed services, and
  deployment infrastructure are out of scope until a measured need is documented.
- UTF-8 JSON export MUST preserve the package identifier and participant name, include exactly one
  answer for every known question ID, preserve input ordering, and reject missing, duplicate, or
  unknown IDs before writing the final artifact.

## Development Workflow and Quality Gates

1. Inventory the current 100 questions by intent family and identify the FOFA fields, operators,
   literals, precedence rules, and external evidence each family requires.
2. Establish verified syntax references and manually reviewed fixtures before implementing a family.
3. Implement schemas and the typed IR, then deterministic normalization, validation, and rendering.
4. Add rule-based translators for unambiguous cases; add the controlled LLM adapter only for semantic
   parsing that rules cannot reliably cover.
5. Require failing tests before each behavior change and passing focused plus full-suite tests after it.
6. Run a two-stage review for formal answers: automated structural/semantic checks, followed by manual
   review of high-risk items such as regex, nested logic, escaping, external research, fingerprints,
   and safe-rejection decisions.
7. Before delivery, verify valid JSON, exact package ID, exact ID set and count, no blank query,
   no explanation or Markdown in query values, and no secrets or unauthorized data.

Changes MUST remain local unless the user explicitly authorizes deployment or publication. Generated
content and rules MUST be based on item-specific evidence; bulk boilerplate generation MUST NOT replace
per-question judgment.

## Governance

This constitution governs all specifications, plans, tasks, implementation, review, and competition
artifacts in this repository. When another project document conflicts with it, this constitution takes
precedence unless the user explicitly amends the constitution.

Amendments MUST document the reason, affected principles, migration impact, and semantic version bump.
Removing or redefining a principle requires a MAJOR bump; adding or materially expanding governance
requires a MINOR bump; non-semantic clarification requires a PATCH bump. Every specification and plan
review MUST include a constitution check, and exceptions MUST be recorded with scope, owner, expiry,
and compensating validation. The Sync Impact Report at the top is review scratch material and SHOULD
be removed before committing an approved amendment.

**Version**: 1.0.0 | **Ratified**: 2026-09-24 | **Last Amended**: 2026-09-24
