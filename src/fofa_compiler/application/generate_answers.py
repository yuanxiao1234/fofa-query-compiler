from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime

from fofa_compiler.application.reject_unsupported import (
    RejectionDecision,
    classify_unsupported,
)
from fofa_compiler.domain.enums import CandidateCreator
from fofa_compiler.domain.errors import ErrorLocation, ValidationError
from fofa_compiler.domain.models import (
    CandidateAnswer,
    CompetitionPackage,
    QueryPayload,
    RejectionPayload,
)
from fofa_compiler.domain.query_validator import validate_query
from fofa_compiler.domain.renderer import normalize, render
from fofa_compiler.domain.risk import assess_risk
from fofa_compiler.infrastructure.audit_log import AuditLog
from fofa_compiler.infrastructure.semantic_parser import SemanticParser
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository
from fofa_compiler.rules.registry import load_rule_data

SAFE_QUESTION_ID = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True, slots=True)
class GenerationItemResult:
    question_id: str
    status: str
    candidate_id: str | None = None
    query: str | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class GenerationSummary:
    job_id: str
    status: str
    total: int
    generated: int
    refused: int
    failed: int
    items: tuple[GenerationItemResult, ...]


def _rules_fingerprint() -> str:
    digest = hashlib.sha256()
    for name in ("fields.yaml", "mappings.yaml"):
        value = load_rule_data(name)
        digest.update(repr(value).encode())
        digest.update(b"\0")
    return digest.hexdigest()


def _candidate_fingerprint(question_fingerprint: str, rule_id: str, query: str) -> str:
    return hashlib.sha256(
        f"{question_fingerprint}\0{_rules_fingerprint()}\0{rule_id}\0{query}".encode()
    ).hexdigest()


def generate_answers(
    *,
    repository: JsonWorkspaceRepository,
    audit_log: AuditLog,
    parser: SemanticParser,
    now: datetime,
    question_id: str | None = None,
) -> GenerationSummary:
    package = repository.load_model("package.json", CompetitionPackage)
    questions = list(package.questions)
    if question_id is not None:
        questions = [question for question in questions if question.question_id == question_id]
        if not questions:
            raise ValidationError(
                "题号不存在",
                location=ErrorLocation(question_id=question_id),
            )

    selection = "\0".join(question.question_id for question in questions)
    job_id = (
        "generate-" + hashlib.sha256(f"{package.run_id}\0{selection}".encode()).hexdigest()[:16]
    )
    results: list[GenerationItemResult] = []

    for question in questions:
        if SAFE_QUESTION_ID.fullmatch(question.question_id) is None:
            results.append(
                GenerationItemResult(
                    question_id=question.question_id,
                    status="failed",
                    error_code="UNSAFE_QUESTION_ID",
                )
            )
            continue
        item_root = f"items/{question.question_id}"
        try:
            decision = classify_unsupported(question.raw_text)
            translated = None
            node = None
            validation_report = None
            if decision is None:
                translated = parser.parse(question.question_id, question.raw_text)
                if translated is None:
                    raise ValidationError(
                        "没有完整匹配该题全部语义的离线规则",
                        location=ErrorLocation(question_id=question.question_id),
                    )
                node = normalize(translated.node)
                validation_report = validate_query(
                    intent=translated.intent,
                    node=node,
                    validated_at=now,
                )
                if not validation_report.is_valid:
                    findings = (
                        validation_report.syntax_checks
                        + validation_report.type_checks
                        + validation_report.coverage_checks
                        + validation_report.logic_checks
                    )
                    decision = RejectionDecision(
                        reason_code="DETERMINISTIC_VALIDATION_FAILED",
                        unsupported_constraints=tuple(item.code for item in findings),
                    )

            if decision is not None:
                query = decision.rejection_text
                rule_id = f"rejection.{decision.reason_code}"
            else:
                assert translated is not None and node is not None
                query = render(node)
                rule_id = translated.rule_id
            fingerprint = _candidate_fingerprint(question.fingerprint, rule_id, query)
            candidate_id = f"candidate-{fingerprint[:20]}"
            current_path = f"{item_root}/current.json"
            existing: CandidateAnswer | None = None
            try:
                existing = repository.load_model(current_path, CandidateAnswer)
            except Exception as exc:
                if (repository.root / current_path).exists():
                    raise exc
            if existing is not None and existing.input_fingerprint == fingerprint:
                candidate = existing
            else:
                revision = 1 if existing is None else existing.revision + 1
                payload: QueryPayload | RejectionPayload
                if decision is not None:
                    payload = RejectionPayload(
                        rejection_text=decision.rejection_text,
                        reason_code=decision.reason_code,
                        unsupported_constraints=decision.unsupported_constraints,
                    )
                else:
                    assert translated is not None and node is not None
                    payload = QueryPayload(
                        intent=translated.intent,
                        ast=node.model_dump(mode="json"),
                        rendered_query=query,
                    )
                candidate = CandidateAnswer(
                    candidate_id=candidate_id,
                    question_id=question.question_id,
                    revision=revision,
                    created_by=CandidateCreator.RULE,
                    input_fingerprint=fingerprint,
                    created_at=now,
                    payload=payload,
                )
                repository.save_model(f"{item_root}/candidates/{revision}.json", candidate)
                repository.save_model(current_path, candidate)
                repository.save_model(f"{item_root}/risks.json", assess_risk(question, candidate))
                if translated is not None:
                    repository.save_model(f"{item_root}/intent.json", translated.intent)
                if validation_report is not None:
                    assert translated is not None and node is not None
                    bound_report = validate_query(
                        intent=translated.intent,
                        node=node,
                        validated_at=now,
                        candidate_id=candidate.candidate_id,
                        revision=revision,
                    )
                    repository.save_model(
                        f"{item_root}/validations/{bound_report.report_id}.json",
                        bound_report,
                    )
                audit_log.append(
                    event_type="candidate.created",
                    occurred_at=now,
                    actor="rule-engine",
                    data={
                        "candidate_id": candidate.candidate_id,
                        "question_id": question.question_id,
                        "revision": revision,
                        "rule_id": rule_id,
                        "rejection_reason": (
                            decision.reason_code if decision is not None else None
                        ),
                    },
                )
            results.append(
                GenerationItemResult(
                    question_id=question.question_id,
                    status="refused" if decision is not None else "generated",
                    candidate_id=candidate.candidate_id,
                    query=query,
                )
            )
        except Exception as exc:
            error_code = exc.code if isinstance(exc, ValidationError) else "GENERATION_ERROR"
            repository.save_json(
                f"{item_root}/generation-error.json",
                {
                    "error_code": error_code,
                    "message": str(exc),
                    "question_id": question.question_id,
                },
            )
            results.append(
                GenerationItemResult(
                    question_id=question.question_id,
                    status="failed",
                    error_code=error_code,
                )
            )

    generated = sum(item.status == "generated" for item in results)
    refused = sum(item.status == "refused" for item in results)
    failed = len(results) - generated - refused
    status = "completed" if failed == 0 else "completed_with_errors"
    job = {
        "schema_version": "1.0",
        "job_id": job_id,
        "kind": "generate",
        "status": status,
        "processed": len(results),
        "total": len(results),
        "counts": {"generated": generated, "refused": refused, "failed": failed},
        "question_ids": [item.question_id for item in results],
    }
    repository.save_json(f"jobs/{job_id}.json", job)
    state = repository.load_json("state.json")
    state["generation"] = job
    repository.save_json("state.json", state)
    return GenerationSummary(
        job_id=job_id,
        status=status,
        total=len(results),
        generated=generated,
        refused=refused,
        failed=failed,
        items=tuple(results),
    )
