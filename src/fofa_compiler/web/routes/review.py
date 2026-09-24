from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from fofa_compiler.application.evidence import EvidenceInput, add_evidence
from fofa_compiler.application.review_answer import amend_answer, confirm_answer
from fofa_compiler.domain.enums import EvidenceSourceKind
from fofa_compiler.domain.models import CandidateAnswer, ValidationReport
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository
from fofa_compiler.web.common import container

router = APIRouter()


def _body_revision(
    repository: JsonWorkspaceRepository, question_id: str, body: dict[str, Any]
) -> CandidateAnswer:
    candidate = repository.load_model(f"items/{question_id}/current.json", CandidateAnswer)
    if body.get("expected_revision") != candidate.revision:
        raise HTTPException(409, "候选版本已变化,请刷新后重试")
    return candidate


@router.put("/api/v1/questions/{question_id}/answer")
async def amend_api(request: Request, question_id: str):  # type: ignore[no-untyped-def]
    body = await request.json()
    app_container = container(request)
    _body_revision(app_container.workspace, question_id, body)
    return amend_answer(
        app_container.workspace,
        question_id,
        str(body.get("query", "")),
        reviewer=str(body.get("reviewer", "")),
        now=app_container.clock.now(),
    ).model_dump(mode="json")


@router.post("/api/v1/questions/{question_id}/confirm")
async def confirm_api(request: Request, question_id: str):  # type: ignore[no-untyped-def]
    body = await request.json()
    app_container = container(request)
    _body_revision(app_container.workspace, question_id, body)
    return confirm_answer(
        app_container.workspace,
        question_id,
        reviewer=str(body.get("reviewer", "")),
        checked_risk_item_ids=tuple(body.get("risk_item_ids", ())),
        reviewed_evidence_ids=tuple(body.get("evidence_ids", ())),
        now=app_container.clock.now(),
    ).model_dump(mode="json")


@router.post("/api/v1/questions/{question_id}/validate")
def validate_api(request: Request, question_id: str):  # type: ignore[no-untyped-def]
    repository = container(request).workspace
    candidate = repository.load_model(f"items/{question_id}/current.json", CandidateAnswer)
    validation_root = repository.root / "items" / question_id / "validations"
    reports = [
        repository.load_model(str(path.relative_to(repository.root)), ValidationReport)
        for path in sorted(validation_root.glob("*.json"))
    ]
    current = [
        report
        for report in reports
        if report.candidate_id == candidate.candidate_id and report.revision == candidate.revision
    ]
    if not current:
        raise HTTPException(409, "当前候选尚无验证结果")
    return current[-1].model_dump(mode="json")


@router.delete("/api/v1/questions/{question_id}/confirmation")
def delete_confirmation(request: Request, question_id: str):  # type: ignore[no-untyped-def]
    path = container(request).workspace.root / "items" / question_id / "final-answer.json"
    if path.is_file():
        archive = path.parent / "final-answers" / "manually-cleared.json"
        archive.parent.mkdir(parents=True, exist_ok=True)
        os.replace(path, archive)
    return {"cleared": True}


@router.post("/api/v1/questions/{question_id}/evidence")
async def evidence_api(request: Request, question_id: str):  # type: ignore[no-untyped-def]
    body = await request.json()
    app_container = container(request)
    record = add_evidence(
        app_container.workspace,
        EvidenceInput(
            question_id=question_id,
            source_kind=EvidenceSourceKind(body["kind"]),
            source_locator=str(body["source"]),
            facts=tuple(body.get("facts", ())),
            content=str(body["content"]).encode() if body.get("content") else None,
            verified_by=body.get("verified_by"),
            original_source_locator=body.get("original_source"),
            equivalence_assessment=body.get("equivalence_assessment"),
        ),
        now=app_container.clock.now(),
    )
    return record.model_dump(mode="json")


@router.get("/evidence/{question_id}")
def evidence_page(request: Request, question_id: str):  # type: ignore[no-untyped-def]
    return request.app.state.templates.TemplateResponse(
        request=request, name="review.html", context={"detail": {"question_id": question_id}}
    )
