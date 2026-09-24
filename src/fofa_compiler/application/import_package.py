from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from fofa_compiler.domain.enums import FindingSeverity
from fofa_compiler.domain.errors import ErrorLocation, InputFormatError, PackageIntegrityError
from fofa_compiler.domain.models import (
    CompetitionPackage,
    Finding,
    Question,
    SourceFile,
    SourceManifest,
    ValidationReport,
)
from fofa_compiler.infrastructure.package_reader import (
    SourceDocument,
    read_json,
    read_package_metadata,
    read_source,
)
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository


@dataclass(frozen=True, slots=True)
class ImportRequest:
    questions_path: Path
    package_path: Path
    template_path: Path


def _require_mapping(value: Any, *, file: Path, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputFormatError(
            "数据项必须是 JSON 对象",
            location=ErrorLocation(file=str(file), json_path=path),
        )
    return value


def _required_text(item: dict[str, Any], key: str, *, file: Path, path: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InputFormatError(
            f"字段 {key} 必须是非空字符串",
            location=ErrorLocation(file=str(file), json_path=f"{path}.{key}"),
        )
    return value.strip()


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicate_values: set[str] = set()
    for value in values:
        if value in seen:
            duplicate_values.add(value)
        seen.add(value)
    return sorted(duplicate_values)


def _source_file(role: str, document: SourceDocument, media_type: str) -> SourceFile:
    return SourceFile(
        role=role,
        source_name=document.path.name,
        media_type=media_type,
        size=len(document.content),
        sha256=document.sha256,
    )


def import_package(
    request: ImportRequest,
    *,
    repository: JsonWorkspaceRepository,
    now: datetime,
) -> CompetitionPackage:
    question_document = read_source(request.questions_path)
    package_document = read_source(request.package_path)
    template_document = read_source(request.template_path)
    questions_value = read_json(question_document)
    template_value = read_json(template_document)
    metadata = read_package_metadata(package_document)

    if not isinstance(questions_value, list) or not questions_value:
        raise InputFormatError(
            "题目文件必须是非空 JSON 数组",
            location=ErrorLocation(file=str(request.questions_path), json_path="$"),
        )
    template = _require_mapping(template_value, file=request.template_path, path="$")
    template_package_id = _required_text(
        template, "参赛包编号", file=request.template_path, path="$"
    )
    answers_value = template.get("答案")
    if not isinstance(answers_value, list) or not answers_value:
        raise InputFormatError(
            "答案字段必须是非空 JSON 数组",
            location=ErrorLocation(file=str(request.template_path), json_path="$.答案"),
        )

    questions: list[Question] = []
    for index, raw_item in enumerate(questions_value):
        item = _require_mapping(raw_item, file=request.questions_path, path=f"$[{index}]")
        question_id = _required_text(
            item, "题号", file=request.questions_path, path=f"$[{index}]"
        )
        raw_text = _required_text(
            item, "自然语言输入", file=request.questions_path, path=f"$[{index}]"
        )
        fingerprint = hashlib.sha256(f"{question_id}\0{raw_text}".encode()).hexdigest()
        questions.append(
            Question(
                question_id=question_id,
                ordinal=index,
                raw_text=raw_text,
                source_location=f"{request.questions_path.name}:$[{index}]",
                fingerprint=fingerprint,
            )
        )

    template_ids: list[str] = []
    for index, raw_item in enumerate(answers_value):
        item = _require_mapping(raw_item, file=request.template_path, path=f"$.答案[{index}]")
        template_ids.append(
            _required_text(item, "题号", file=request.template_path, path=f"$.答案[{index}]")
        )

    question_ids = [item.question_id for item in questions]
    details: list[dict[str, Any]] = []
    if duplicate_ids := _duplicates(question_ids):
        details.append({"code": "DUPLICATE_QUESTION_IDS", "question_ids": duplicate_ids})
    if duplicate_ids := _duplicates(template_ids):
        details.append({"code": "DUPLICATE_TEMPLATE_IDS", "question_ids": duplicate_ids})
    missing_ids = sorted(set(question_ids) - set(template_ids))
    unknown_ids = sorted(set(template_ids) - set(question_ids))
    if missing_ids:
        details.append({"code": "MISSING_TEMPLATE_IDS", "question_ids": missing_ids})
    if unknown_ids:
        details.append({"code": "UNKNOWN_TEMPLATE_IDS", "question_ids": unknown_ids})
    if metadata.package_id != template_package_id:
        details.append(
            {
                "code": "PACKAGE_ID_MISMATCH",
                "package_id": metadata.package_id,
                "template_package_id": template_package_id,
            }
        )
    if details:
        raise PackageIntegrityError("参赛包完整性校验失败", details=details)

    combined_digest = hashlib.sha256(
        question_document.content
        + b"\0"
        + package_document.content
        + b"\0"
        + template_document.content
    ).hexdigest()
    run_id = f"{metadata.package_id}-{combined_digest[:12]}"
    report = ValidationReport(
        report_id=f"import-{combined_digest[:16]}",
        validator_version="package-import/1",
        is_valid=True,
        validated_at=now,
        input_checks=(
            Finding(
                code="PACKAGE_VALID",
                severity=FindingSeverity.INFO,
                message=f"参赛包校验通过,共 {len(questions)} 道题",
            ),
        ),
    )
    package = CompetitionPackage(
        run_id=run_id,
        package_id=metadata.package_id,
        issued_at=metadata.issued_at,
        participant_name=None,
        source_manifest=SourceManifest(
            files=(
                _source_file("questions", question_document, "application/json"),
                _source_file("package", package_document, "text/plain"),
                _source_file("template", template_document, "application/json"),
            )
        ),
        questions=tuple(questions),
        template_question_ids=tuple(template_ids),
        original_order=tuple(question_ids),
        rules_fingerprint="0" * 64,
        import_report=report,
        created_at=now,
    )
    repository.save_model("package.json", package)
    repository.save_json(
        "state.json",
        {
            "schema_version": "1.0",
            "run_id": run_id,
            "package_id": metadata.package_id,
            "question_count": len(questions),
            "status": "in_progress",
        },
    )
    repository.save_json(
        "import-report.json", report.model_dump(mode="json", by_alias=True)
    )
    return package
