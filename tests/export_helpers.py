from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from fofa_compiler.domain.enums import (
    CandidateCreator,
    ReviewDecision,
    RiskLevel,
)
from fofa_compiler.domain.models import (
    CandidateAnswer,
    CompetitionPackage,
    FinalAnswer,
    Question,
    RejectionPayload,
    ReviewRecord,
    RiskAssessment,
    SourceManifest,
    ValidationReport,
)
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository

NOW = datetime(2026, 9, 24, 8, tzinfo=UTC)


def seed_exportable_workspace(
    repository: JsonWorkspaceRepository, count: int = 3
) -> CompetitionPackage:
    questions = tuple(
        Question(
            question_id=f"Q{index:03d}",
            ordinal=index - 1,
            raw_text=f"测试题 {index}",
            source_location=f"questions.json:$[{index - 1}]",
            fingerprint=hashlib.sha256(str(index).encode()).hexdigest(),
        )
        for index in range(1, count + 1)
    )
    ids = tuple(question.question_id for question in questions)
    package = CompetitionPackage(
        run_id="run-export",
        package_id="pkg-export",
        source_manifest=SourceManifest(files=()),
        questions=questions,
        template_question_ids=ids,
        original_order=ids,
        rules_fingerprint="0" * 64,
        import_report=ValidationReport(
            report_id="import-valid",
            validator_version="test/1",
            is_valid=True,
            validated_at=NOW,
        ),
        created_at=NOW,
    )
    repository.save_model("package.json", package)
    for question in questions:
        qid = question.question_id
        candidate = CandidateAnswer(
            candidate_id=f"candidate-{qid}",
            question_id=qid,
            revision=1,
            created_by=CandidateCreator.RULE,
            input_fingerprint=hashlib.sha256(qid.encode()).hexdigest(),
            created_at=NOW,
            payload=RejectionPayload(
                rejection_text="该需求不能直接转换为FOFA搜索语句",
                reason_code="TEST_REJECTION",
            ),
        )
        report = ValidationReport(
            report_id=f"validation-{qid}",
            candidate_id=candidate.candidate_id,
            revision=1,
            validator_version="test/1",
            is_valid=True,
            validated_at=NOW,
        )
        review = ReviewRecord(
            review_id=f"review-{qid}",
            question_id=qid,
            candidate_revision=1,
            validation_report_id=report.report_id,
            reviewer="人工复核员",
            decision=ReviewDecision.CONFIRMED,
            confirmed_at=NOW,
        )
        final = FinalAnswer(
            question_id=qid,
            candidate_revision=1,
            answer_kind="rejection",
            query_text=candidate.payload.rejection_text,
            validation_report_id=report.report_id,
            review_record_id=review.review_id,
            finalized_at=NOW,
            finalization_fingerprint=hashlib.sha256(f"final-{qid}".encode()).hexdigest(),
        )
        root = f"items/{qid}"
        repository.save_model(f"{root}/current.json", candidate)
        repository.save_model(f"{root}/validations/{report.report_id}.json", report)
        repository.save_model(f"{root}/reviews/{review.review_id}.json", review)
        repository.save_model(
            f"{root}/risks.json",
            RiskAssessment(
                question_id=qid,
                risk_level=RiskLevel.LOW,
                assessment_version="test/1",
            ),
        )
        repository.save_model(f"{root}/final-answer.json", final)
    return package
