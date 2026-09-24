from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fofa_compiler.application.export_gates import preflight_export
from fofa_compiler.domain.errors import AtomicWriteError, ErrorLocation, ExportBlockedError
from fofa_compiler.domain.models import AnswerItem, AnswerSheet, CompetitionPackage
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository

MAX_EXPORT_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ExportSummary:
    output_path: str
    answer_count: int
    byte_size: int


def _atomic_create(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        descriptor, raw_path = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        temporary = Path(raw_path)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, target)
        temporary.unlink()
        temporary = None
        directory_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except FileExistsError as exc:
        raise ExportBlockedError(
            "输出文件已存在,禁止覆盖", location=ErrorLocation(file=str(target))
        ) from exc
    except OSError as exc:
        raise AtomicWriteError(
            "无法原子写入导出文件", location=ErrorLocation(file=str(target))
        ) from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def export_answers(
    repository: JsonWorkspaceRepository,
    *,
    participant_name: str,
    output_path: Path,
) -> ExportSummary:
    participant = participant_name.strip()
    if not participant:
        raise ExportBlockedError("选手名称不能为空")
    if output_path.exists():
        raise ExportBlockedError(
            "输出文件已存在,禁止覆盖", location=ErrorLocation(file=str(output_path))
        )

    preflight = preflight_export(repository)
    if not preflight.ready:
        raise ExportBlockedError(
            "导出前置检查失败",
            details=[
                {
                    "code": blocker.code,
                    "message": blocker.message,
                    "question_id": blocker.question_id,
                }
                for blocker in preflight.blockers
            ],
        )
    package = repository.load_model("package.json", CompetitionPackage)
    answers_by_id = {answer.question_id: answer for answer in preflight.final_answers}
    sheet = AnswerSheet(
        participant_name=participant,
        package_id=package.package_id,
        answers=tuple(
            AnswerItem(question_id=qid, query=answers_by_id[qid].query_text)
            for qid in package.original_order
        ),
    )
    data = (
        json.dumps(
            sheet.model_dump(mode="json", by_alias=True),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )
    if len(data) >= MAX_EXPORT_BYTES:
        raise ExportBlockedError(
            "导出文件必须小于 8 MB",
            details=[{"code": "EXPORT_TOO_LARGE", "byte_size": len(data)}],
        )
    _atomic_create(output_path.resolve(), data)
    return ExportSummary(str(output_path.resolve()), len(sheet.answers), len(data))
