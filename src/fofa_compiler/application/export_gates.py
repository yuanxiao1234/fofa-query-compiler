from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fofa_compiler.domain.enums import ReviewDecision, RiskLevel
from fofa_compiler.domain.errors import FofaCompilerError
from fofa_compiler.domain.models import (
    CandidateAnswer,
    CompetitionPackage,
    EvidenceRecord,
    FinalAnswer,
    ReviewRecord,
    RiskAssessment,
    ValidationReport,
)
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository

ExportRecord = (
    CandidateAnswer
    | FinalAnswer
    | ReviewRecord
    | RiskAssessment
    | ValidationReport
    | EvidenceRecord
)


@dataclass(frozen=True, slots=True)
class ExportBlocker:
    code: str
    message: str
    question_id: str | None = None


@dataclass(frozen=True, slots=True)
class ExportPreflight:
    ready: bool
    blockers: tuple[ExportBlocker, ...]
    final_answers: tuple[FinalAnswer, ...]


def _load_or_block(
    repository: JsonWorkspaceRepository,
    path: str,
    model_type: type[CandidateAnswer]
    | type[FinalAnswer]
    | type[ReviewRecord]
    | type[RiskAssessment]
    | type[ValidationReport]
    | type[EvidenceRecord],
    *,
    code: str,
    message: str,
    question_id: str,
    blockers: list[ExportBlocker],
) -> ExportRecord | None:
    if not (repository.root / path).is_file():
        blockers.append(ExportBlocker(code, message, question_id))
        return None
    try:
        return repository.load_model(path, model_type)
    except FofaCompilerError:
        blockers.append(ExportBlocker(code, f"{message}(记录损坏)", question_id))
        return None


def _unknown_final_answer_ids(root: Path, expected: set[str]) -> list[str]:
    items_root = root / "items"
    if not items_root.is_dir():
        return []
    return sorted(
        item.name
        for item in items_root.iterdir()
        if item.is_dir() and item.name not in expected and (item / "final-answer.json").is_file()
    )


def preflight_export(repository: JsonWorkspaceRepository) -> ExportPreflight:
    package = repository.load_model("package.json", CompetitionPackage)
    blockers: list[ExportBlocker] = []
    final_answers: list[FinalAnswer] = []
    expected_ids = set(package.original_order)

    for unknown_id in _unknown_final_answer_ids(repository.root, expected_ids):
        blockers.append(
            ExportBlocker("UNKNOWN_FINAL_ANSWER_ID", "存在参赛包之外的最终答案", unknown_id)
        )

    for question in package.questions:
        qid = question.question_id
        root = f"items/{qid}"
        final = _load_or_block(
            repository,
            f"{root}/final-answer.json",
            FinalAnswer,
            code="MISSING_FINAL_ANSWER",
            message="缺少最终答案",
            question_id=qid,
            blockers=blockers,
        )
        candidate = _load_or_block(
            repository,
            f"{root}/current.json",
            CandidateAnswer,
            code="MISSING_CURRENT_CANDIDATE",
            message="缺少当前候选答案",
            question_id=qid,
            blockers=blockers,
        )
        risk = _load_or_block(
            repository,
            f"{root}/risks.json",
            RiskAssessment,
            code="MISSING_RISK_ASSESSMENT",
            message="缺少风险评估",
            question_id=qid,
            blockers=blockers,
        )
        if not isinstance(final, FinalAnswer):
            continue
        final_answers.append(final)
        if final.question_id != qid:
            blockers.append(ExportBlocker("FINAL_ANSWER_ID_MISMATCH", "最终答案题号不匹配", qid))
        if not final.query_text.strip():
            blockers.append(ExportBlocker("EMPTY_ANSWER", "最终查询语句为空", qid))
        if isinstance(candidate, CandidateAnswer):
            expected_text = (
                candidate.payload.rendered_query
                if candidate.payload.kind == "query"
                else candidate.payload.rejection_text
            )
            if final.candidate_revision != candidate.revision or final.query_text != expected_text:
                blockers.append(
                    ExportBlocker("STALE_FINAL_ANSWER", "最终答案未绑定当前候选版本", qid)
                )

        validation = _load_or_block(
            repository,
            f"{root}/validations/{final.validation_report_id}.json",
            ValidationReport,
            code="MISSING_VALIDATION",
            message="缺少最终答案引用的验证报告",
            question_id=qid,
            blockers=blockers,
        )
        if isinstance(validation, ValidationReport) and (
            not validation.is_valid
            or not isinstance(candidate, CandidateAnswer)
            or validation.candidate_id != candidate.candidate_id
            or validation.revision != candidate.revision
        ):
            blockers.append(ExportBlocker("STALE_OR_FAILED_VALIDATION", "验证未通过或已过期", qid))

        review = _load_or_block(
            repository,
            f"{root}/reviews/{final.review_record_id}.json",
            ReviewRecord,
            code="MISSING_CONFIRMATION",
            message="缺少人工确认记录",
            question_id=qid,
            blockers=blockers,
        )
        if isinstance(review, ReviewRecord) and (
            review.question_id != qid
            or review.decision is not ReviewDecision.CONFIRMED
            or review.confirmed_at is None
            or review.candidate_revision != final.candidate_revision
            or review.validation_report_id != final.validation_report_id
        ):
            blockers.append(
                ExportBlocker("STALE_OR_INVALID_CONFIRMATION", "人工确认无效或已过期", qid)
            )

        if isinstance(risk, RiskAssessment):
            required_items = {item.item_id for item in risk.risk_items if item.required}
            unresolved = {
                item.item_id for item in risk.risk_items if item.required and not item.resolved
            }
            checked = (
                set(review.checked_risk_item_ids) if isinstance(review, ReviewRecord) else set()
            )
            if risk.risk_level is RiskLevel.HIGH and (unresolved or not required_items <= checked):
                blockers.append(
                    ExportBlocker("INCOMPLETE_HIGH_RISK_CHECKS", "高风险检查项未全部完成", qid)
                )

            evidence_required = question.requires_external_evidence or risk.requires_evidence_review
            reviewed_ids = review.reviewed_evidence_ids if isinstance(review, ReviewRecord) else ()
            sufficient = bool(reviewed_ids)
            for evidence_id in reviewed_ids:
                evidence = _load_or_block(
                    repository,
                    f"evidence/{qid}/{evidence_id}.json",
                    EvidenceRecord,
                    code="INSUFFICIENT_EVIDENCE",
                    message="复核引用的证据缺失",
                    question_id=qid,
                    blockers=blockers,
                )
                sufficient = (
                    sufficient and isinstance(evidence, EvidenceRecord) and evidence.is_sufficient
                )
            if evidence_required and not sufficient:
                blockers.append(ExportBlocker("INSUFFICIENT_EVIDENCE", "外部证据不足或受阻", qid))

    return ExportPreflight(
        ready=not blockers and len(final_answers) == len(package.questions),
        blockers=tuple(blockers),
        final_answers=tuple(final_answers),
    )
