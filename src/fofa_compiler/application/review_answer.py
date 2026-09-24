from __future__ import annotations

import hashlib
import os
from datetime import datetime

from pydantic import TypeAdapter

from fofa_compiler.domain.enums import CandidateCreator, FindingSeverity, ReviewDecision, RiskLevel
from fofa_compiler.domain.errors import ErrorLocation, ValidationError
from fofa_compiler.domain.ir import QueryNode
from fofa_compiler.domain.models import (
    CandidateAnswer,
    CompetitionPackage,
    EvidenceRecord,
    FinalAnswer,
    Finding,
    QueryPayload,
    RejectionPayload,
    ReviewRecord,
    RiskAssessment,
    ValidationReport,
)
from fofa_compiler.domain.query_validator import validate_query
from fofa_compiler.domain.renderer import render
from fofa_compiler.domain.risk import assess_risk
from fofa_compiler.infrastructure.audit_log import AuditLog
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository

NODE_ADAPTER: TypeAdapter[QueryNode] = TypeAdapter(QueryNode)


def _question(package: CompetitionPackage, question_id: str):  # type: ignore[no-untyped-def]
    for question in package.questions:
        if question.question_id == question_id:
            return question
    raise ValidationError("题号不存在", location=ErrorLocation(question_id=question_id))


def _invalidate_final(repository: JsonWorkspaceRepository, question_id: str, revision: int) -> None:
    current = repository.root / "items" / question_id / "final-answer.json"
    if current.is_file():
        archive = current.parent / "final-answers" / f"stale-before-{revision}.json"
        archive.parent.mkdir(parents=True, exist_ok=True)
        os.replace(current, archive)


def amend_answer(
    repository: JsonWorkspaceRepository,
    question_id: str,
    query_text: str,
    *,
    reviewer: str,
    now: datetime,
) -> CandidateAnswer:
    if not reviewer.strip() or not query_text.strip():
        raise ValidationError("复核者和修订查询不能为空")
    package = repository.load_model("package.json", CompetitionPackage)
    question = _question(package, question_id)
    current = repository.load_model(f"items/{question_id}/current.json", CandidateAnswer)
    revision = current.revision + 1
    text = query_text.strip()
    fingerprint = hashlib.sha256(
        f"{current.input_fingerprint}\0{revision}\0{text}".encode()
    ).hexdigest()

    if current.payload.kind == "rejection" and text == current.payload.rejection_text:
        payload: QueryPayload | RejectionPayload = RejectionPayload(
            rejection_text=text,
            reason_code=current.payload.reason_code,
            unsupported_constraints=current.payload.unsupported_constraints,
            evidence_refs=current.payload.evidence_refs,
        )
        report = ValidationReport(
            report_id="validation-" + fingerprint[:20],
            candidate_id="candidate-" + fingerprint[:20],
            revision=revision,
            validator_version="query-validator/1",
            is_valid=True,
            validated_at=now,
        )
    elif current.payload.kind == "query":
        node = NODE_ADAPTER.validate_python(current.payload.ast)
        payload = current.payload.model_copy(update={"rendered_query": text})
        report = validate_query(
            intent=current.payload.intent,
            node=node,
            validated_at=now,
            candidate_id="candidate-" + fingerprint[:20],
            revision=revision,
        )
        if text != render(node):
            finding = Finding(
                code="MANUAL_QUERY_AST_MISMATCH",
                severity=FindingSeverity.ERROR,
                message="手工查询与结构化 AST 不一致,需要结构化修订",
                blocking=True,
            )
            report = report.model_copy(
                update={"syntax_checks": (*report.syntax_checks, finding), "is_valid": False}
            )
    else:
        raise ValidationError("拒绝答案只能保持固定拒绝文本")

    candidate = CandidateAnswer(
        candidate_id="candidate-" + fingerprint[:20],
        question_id=question_id,
        revision=revision,
        created_by=CandidateCreator.REVIEWER,
        input_fingerprint=fingerprint,
        created_at=now,
        payload=payload,
    )
    repository.save_model(f"items/{question_id}/candidates/{revision}.json", candidate)
    repository.save_model(f"items/{question_id}/current.json", candidate)
    repository.save_model(f"items/{question_id}/validations/{report.report_id}.json", report)
    repository.save_model(f"items/{question_id}/risks.json", assess_risk(question, candidate))
    _invalidate_final(repository, question_id, revision)
    AuditLog(repository.root / "audit" / "events.jsonl").append(
        event_type="candidate.amended",
        occurred_at=now,
        actor=reviewer.strip(),
        data={
            "question_id": question_id,
            "revision": revision,
            "candidate_id": candidate.candidate_id,
        },
    )
    return candidate


def _current_validation(
    repository: JsonWorkspaceRepository, question_id: str, candidate: CandidateAnswer
) -> ValidationReport:
    root = repository.root / "items" / question_id / "validations"
    reports = (
        [
            repository.load_model(str(path.relative_to(repository.root)), ValidationReport)
            for path in sorted(root.glob("*.json"))
        ]
        if root.is_dir()
        else []
    )
    matches = [
        report
        for report in reports
        if report.candidate_id == candidate.candidate_id and report.revision == candidate.revision
    ]
    if not matches or not matches[-1].is_valid:
        raise ValidationError("当前候选缺少有效且未过期的验证报告")
    return matches[-1]


def confirm_answer(
    repository: JsonWorkspaceRepository,
    question_id: str,
    *,
    reviewer: str,
    checked_risk_item_ids: tuple[str, ...],
    reviewed_evidence_ids: tuple[str, ...],
    now: datetime,
) -> FinalAnswer:
    if not reviewer.strip():
        raise ValidationError("复核者不能为空")
    package = repository.load_model("package.json", CompetitionPackage)
    _question(package, question_id)
    candidate = repository.load_model(f"items/{question_id}/current.json", CandidateAnswer)
    validation = _current_validation(repository, question_id, candidate)
    risk = repository.load_model(f"items/{question_id}/risks.json", RiskAssessment)
    required_ids = {item.item_id for item in risk.risk_items if item.required}
    checked = set(checked_risk_item_ids)
    if risk.risk_level == RiskLevel.HIGH and not required_ids <= checked:
        raise ValidationError("高风险检查项未全部确认")

    evidence_records: list[EvidenceRecord] = []
    for evidence_id in reviewed_evidence_ids:
        evidence_records.append(
            repository.load_model(f"evidence/{question_id}/{evidence_id}.json", EvidenceRecord)
        )
    if risk.requires_evidence_review and (
        not evidence_records or not all(item.is_sufficient for item in evidence_records)
    ):
        raise ValidationError("所需证据尚未充分核验")

    resolved_risk = risk.model_copy(
        update={
            "risk_items": tuple(
                item.model_copy(
                    update={
                        "resolved": True,
                        "resolved_by": reviewer.strip(),
                        "resolved_at": now,
                    }
                )
                if item.item_id in checked
                else item
                for item in risk.risk_items
            )
        }
    )
    repository.save_model(f"items/{question_id}/risks.json", resolved_risk)
    seed = f"{question_id}\0{candidate.revision}\0{reviewer.strip()}\0{now.isoformat()}"
    review_id = "review-" + hashlib.sha256(seed.encode()).hexdigest()[:20]
    review = ReviewRecord(
        review_id=review_id,
        question_id=question_id,
        candidate_revision=candidate.revision,
        validation_report_id=validation.report_id,
        reviewer=reviewer.strip(),
        decision=ReviewDecision.CONFIRMED,
        reviewed_evidence_ids=reviewed_evidence_ids,
        checked_risk_item_ids=checked_risk_item_ids,
        confirmed_at=now,
    )
    repository.save_model(f"items/{question_id}/reviews/{review_id}.json", review)
    text = (
        candidate.payload.rendered_query
        if candidate.payload.kind == "query"
        else candidate.payload.rejection_text
    )
    final_fingerprint = hashlib.sha256(
        f"{candidate.candidate_id}\0{validation.report_id}\0{review_id}\0{text}".encode()
    ).hexdigest()
    final = FinalAnswer(
        question_id=question_id,
        candidate_revision=candidate.revision,
        answer_kind=candidate.payload.kind,
        query_text=text,
        validation_report_id=validation.report_id,
        review_record_id=review_id,
        finalized_at=now,
        finalization_fingerprint=final_fingerprint,
    )
    repository.save_model(f"items/{question_id}/final-answer.json", final)
    AuditLog(repository.root / "audit" / "events.jsonl").append(
        event_type="answer.confirmed",
        occurred_at=now,
        actor=reviewer.strip(),
        data={"question_id": question_id, "revision": candidate.revision, "review_id": review_id},
    )
    return final
