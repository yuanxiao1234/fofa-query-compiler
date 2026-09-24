from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from fofa_compiler.domain.models import (
    CandidateAnswer,
    CompetitionPackage,
    EvidenceRecord,
    FinalAnswer,
    RiskAssessment,
    ValidationReport,
)
from fofa_compiler.web.common import container, model_json, package_or_none, relative_json_paths

router = APIRouter()


def _items(request: Request) -> list[dict[str, object]]:
    repository = container(request).workspace
    package = repository.load_model("package.json", CompetitionPackage)
    values: list[dict[str, object]] = []
    for question in package.questions:
        root = repository.root / "items" / question.question_id
        risk = (
            repository.load_model(f"items/{question.question_id}/risks.json", RiskAssessment)
            if (root / "risks.json").is_file()
            else None
        )
        validation_paths = sorted((root / "validations").glob("*.json"))
        validations = [
            repository.load_model(str(path.relative_to(repository.root)), ValidationReport)
            for path in validation_paths
        ]
        validation = "passed" if validations and validations[-1].is_valid else "failed"
        if not validations:
            validation = "not_run"
        evidence_records = [
            repository.load_model(str(path.relative_to(repository.root)), EvidenceRecord)
            for path in sorted((repository.root / "evidence" / question.question_id).glob("*.json"))
        ]
        evidence = "not_required"
        if risk and risk.requires_evidence_review:
            evidence = (
                "sufficient" if any(item.is_sufficient for item in evidence_records) else "blocked"
            )
        values.append(
            {
                "question_id": question.question_id,
                "raw_text": question.raw_text,
                "risk": risk.risk_level.value if risk else "unknown",
                "confirmed": (root / "final-answer.json").is_file(),
                "evidence_required": bool(risk and risk.requires_evidence_review),
                "evidence": evidence,
                "validation": validation,
            }
        )
    return values


@router.get("/questions")
def questions_page(request: Request):  # type: ignore[no-untyped-def]
    return request.app.state.templates.TemplateResponse(
        request=request, name="questions.html", context={"items": _items(request)}
    )


@router.get("/api/v1/questions")
def questions_api(
    request: Request,
    risk: str | None = None,
    status: str | None = None,
    evidence: str | None = None,
    validation: str | None = None,
    question_id: str | None = None,
) -> dict[str, object]:
    items = _items(request)
    if risk:
        items = [item for item in items if item["risk"] == risk]
    if status == "confirmed":
        items = [item for item in items if item["confirmed"]]
    if status == "unconfirmed":
        items = [item for item in items if not item["confirmed"]]
    if question_id:
        items = [item for item in items if question_id in str(item["question_id"])]
    if evidence:
        items = [item for item in items if item["evidence"] == evidence]
    if validation:
        items = [item for item in items if item["validation"] == validation]
    items.sort(key=lambda item: (bool(item["confirmed"]), item["question_id"]))
    return {"items": items, "total": len(items)}


def _detail(request: Request, question_id: str) -> dict[str, object]:
    repository = container(request).workspace
    package = repository.load_model("package.json", CompetitionPackage)
    question = next((item for item in package.questions if item.question_id == question_id), None)
    if question is None:
        raise HTTPException(404, "题号不存在")
    base = f"items/{question_id}"
    candidate = repository.load_model(f"{base}/current.json", CandidateAnswer)
    risk = repository.load_model(f"{base}/risks.json", RiskAssessment)
    validations = [
        repository.load_model(path, ValidationReport)
        for path in relative_json_paths(repository.root, f"{base}/validations/*.json")
    ]
    evidence = [
        repository.load_model(path, EvidenceRecord)
        for path in relative_json_paths(repository.root, f"evidence/{question_id}/*.json")
    ]
    final_path = repository.root / base / "final-answer.json"
    final = (
        repository.load_model(f"{base}/final-answer.json", FinalAnswer)
        if final_path.is_file()
        else None
    )
    return {
        "question": model_json(question),
        "candidate": model_json(candidate),
        "risk": model_json(risk),
        "validations": [model_json(item) for item in validations],
        "evidence": [model_json(item) for item in evidence],
        "final": model_json(final),
    }


@router.get("/api/v1/questions/{question_id}")
def question_api(request: Request, question_id: str):  # type: ignore[no-untyped-def]
    return _detail(request, question_id)


@router.get("/questions/{question_id}")
def question_page(request: Request, question_id: str):  # type: ignore[no-untyped-def]
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="review.html",
        context={"detail": _detail(request, question_id)},
    )


@router.get("/api/v1/status")
def status_api(request: Request):  # type: ignore[no-untyped-def]
    package = package_or_none(request)
    items = _items(request) if package else []
    return {
        "package_id": package.package_id if package else None,
        "total": len(items),
        "confirmed": sum(bool(item["confirmed"]) for item in items),
        "completed": sum(bool(item["confirmed"]) for item in items),
        "processing": 0,
        "failed": sum(item["validation"] == "failed" for item in items),
        "blocked": sum(item["evidence"] == "blocked" for item in items),
        "csrf_token": request.app.state.csrf_token,
    }
