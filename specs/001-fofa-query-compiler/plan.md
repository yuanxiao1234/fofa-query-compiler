# Implementation Plan: FOFA Natural-Language Query Compiler

**Branch**: `001-fofa-query-compiler` | **Date**: 2026-09-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-fofa-query-compiler/spec.md`

## Summary

Build a local, single-user FOFA query compiler that imports a competition package, converts each
natural-language request into a typed intent and AST, validates every atomic constraint, routes risky
or evidence-dependent items through review, and exports only a complete confirmed answer sheet. The
first release provides both an independent CLI and a localhost Web UI. Both adapters call the same
application services and use the same versioned file workspace, deterministic renderer, validation
pipeline, evidence rules, review state, and export gate.

The translation strategy is rule-first: deterministic rules handle unambiguous intent families, while
an optional provider adapter may propose structured IR for complex language. A model never emits the
final query. The Web UI uses server-rendered pages and incremental updates to prioritize rapid delivery
without adding a separate frontend build or a second implementation of business rules.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: Pydantic v2; FastAPI; Uvicorn; Jinja2; python-multipart; locally vendored
HTMX; optional provider adapter dependencies installed as extras. Lark is deferred unless the tested
hand-written parser cannot safely cover the supported FOFA subset.

**Storage**: Versioned UTF-8 JSON/JSONL run workspaces with SHA-256 fingerprints, immutable candidate
revisions, an append-only audit event stream, and atomic file replacement; no database in v1.

**Testing**: pytest, Hypothesis, pytest-cov, FastAPI contract tests, template/rendering tests, SSE tests,
and a minimal browser end-to-end suite for the critical Web workflow.

**Target Platform**: Local macOS and Linux on CPython 3.12+; browser access only through a localhost
server bound to `127.0.0.1` by default.

**Project Type**: Modular monolith/compiler with two adapters: local CLI and local server-rendered Web UI.

**Performance Goals**: Import, automatic generation, validation, and creation of the review queue for
100 prepared questions completes within 10 minutes excluding external evidence and human review;
95% of local list/filter/detail interactions render within 1 second; visible generation progress is
updated within 2 seconds.

**Constraints**: Core rules, validation, review, and export work without FOFA credentials or a live
model; final JSON is below 8 MB; every question requires human confirmation; high-risk items also
require completed evidence and risk checks; blocked evidence prevents export; writes are atomic;
Web and CLI results must be identical for the same workspace; no deployment or public binding.

**Scale/Scope**: One local user, one active generation task per run, current packages of 100 questions,
multiple recoverable local runs, and a versioned FOFA subset sufficient for the current intent catalog.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Gate | Pre-Research | Post-Design Evidence |
|------|--------------|----------------------|
| Accuracy and source fidelity | PASS | Atomic constraints, field registry, evidence records, semantic coverage checks, and blocked-evidence state prevent guessed or incomplete output. |
| Typed intermediate representation | PASS | `NormalizedIntent` is separate from a discriminated `QueryAST`; only the deterministic renderer produces FOFA text. |
| Deterministic validation and safe rejection | PASS | Layered validators cover structure, types, ranges, logic, semantic coverage, and exact rejection text. Evidence failure remains blocked rather than misclassified as rejection. |
| Evidence-based evaluation | PASS | Intent-family fixtures, 100-item end-to-end checks, all-or-nothing semantic scoring, and independent benchmark judgements are part of the design. |
| Reproducible and auditable output | PASS | Input/configuration/evidence fingerprints, immutable revisions, append-only events, stable rendering, and isolated exports support replay and audit. |
| Python 3.12 and Pydantic v2 | PASS | Both are mandatory technical foundations. |
| Local CLI as a primary surface | PASS | CLI remains independently runnable and shares application services with the Web UI. |
| Web UI scope condition | PASS | The user's urgent first-release request is documented in the specification as the measured need allowed by the constitution; public deployment and multi-user scope remain excluded. |
| Local-only deployment rule | PASS | The design binds to localhost and creates no deployment artifact or hosted environment. |
| Item-specific evidence and review | PASS | Per-question intent, evidence, validation, risk checklist, and confirmation records prohibit template-based bulk judgement. |

No constitution violation requires an exception. Phase 0 research resolved dependency, parser, storage,
adapter, UI, progress, and testing choices. The Phase 1 data model and contracts retain all gates.

## Project Structure

### Documentation (this feature)

```text
specs/001-fofa-query-compiler/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   ├── web.md
│   └── workspace.md
└── tasks.md                 # Created later by speckit-tasks
```

### Source Code (repository root)

```text
pyproject.toml
src/
└── fofa_compiler/
    ├── domain/
    │   ├── models.py
    │   ├── intent.py
    │   ├── ast.py
    │   ├── states.py
    │   └── findings.py
    ├── application/
    │   ├── import_package.py
    │   ├── generate_candidates.py
    │   ├── validate_candidate.py
    │   ├── manage_evidence.py
    │   ├── review_answer.py
    │   ├── export_sheet.py
    │   └── query_status.py
    ├── compiler/
    │   ├── normalizer.py
    │   ├── translator.py
    │   ├── renderer.py
    │   ├── parser.py
    │   └── validators/
    ├── rules/
    │   ├── registry.py
    │   ├── intent_families/
    │   └── vocabularies/
    ├── adapters/
    │   ├── llm/
    │   ├── evidence/
    │   └── package_formats/
    ├── infrastructure/
    │   ├── workspace_repository.py
    │   ├── event_store.py
    │   ├── locking.py
    │   └── hashing.py
    ├── cli/
    │   └── main.py
    └── web/
        ├── app.py
        ├── routes/
        ├── templates/
        └── static/
data/
├── field-catalog/
├── rules/
├── vocabularies/
└── fixtures/
tests/
├── contract/
├── integration/
├── e2e/
├── fixtures/
├── property/
└── unit/
```

**Structure Decision**: Use one installable Python package with strict domain/application/adapter
boundaries. CLI and Web are thin adapters; neither owns translation, validation, state transitions,
or export logic. Versioned field/rule/evidence data stays outside prompts and application branches.
The Web UI is server-rendered from the same process, so v1 needs neither Node tooling nor a separate
frontend service. Runtime workspaces and exports live under a user-selected local directory and are
excluded from source control.

## Complexity Tracking

No constitution violations require justification. The local Web UI is an explicitly requested v1
surface and remains inside the same modular monolith; it does not introduce a second product, database,
public API, deployment target, or duplicated business layer.
