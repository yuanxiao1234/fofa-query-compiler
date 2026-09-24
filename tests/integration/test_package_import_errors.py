import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from fofa_compiler.application.import_package import ImportRequest, import_package
from fofa_compiler.domain.errors import InputFormatError, PackageIntegrityError
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository


def write_package(tmp_path: Path, questions: object, answer_ids: list[str]) -> ImportRequest:
    questions_path = tmp_path / "questions.json"
    package_path = tmp_path / "package.txt"
    template_path = tmp_path / "template.json"
    questions_path.write_text(json.dumps(questions, ensure_ascii=False), encoding="utf-8")
    package_path.write_text("pkg-test\n2026-09-24T08:00:00+08:00\n", encoding="utf-8")
    template_path.write_text(
        json.dumps(
            {
                "选手名称": "",
                "参赛包编号": "pkg-test",
                "答案": [{"题号": question_id, "查询语句": ""} for question_id in answer_ids],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return ImportRequest(questions_path, package_path, template_path)


def execute(request: ImportRequest, tmp_path: Path):  # type: ignore[no-untyped-def]
    return import_package(
        request,
        repository=JsonWorkspaceRepository(tmp_path / "workspace"),
        now=datetime(2026, 9, 24, tzinfo=UTC),
    )


def test_invalid_json_reports_file(tmp_path: Path) -> None:
    request = write_package(tmp_path, [], ["Q1"])
    request.questions_path.write_text("[", encoding="utf-8")
    with pytest.raises(InputFormatError) as caught:
        execute(request, tmp_path)
    assert caught.value.location.file == str(request.questions_path)


def test_reports_duplicate_missing_and_unknown_ids_together(tmp_path: Path) -> None:
    request = write_package(
        tmp_path,
        [
            {"题号": "Q1", "自然语言输入": "a"},
            {"题号": "Q1", "自然语言输入": "b"},
            {"题号": "Q2", "自然语言输入": "c"},
        ],
        ["Q1", "Q3", "Q3"],
    )
    with pytest.raises(PackageIntegrityError) as caught:
        execute(request, tmp_path)
    codes = {detail["code"] for detail in caught.value.details}
    assert codes == {
        "DUPLICATE_QUESTION_IDS",
        "DUPLICATE_TEMPLATE_IDS",
        "MISSING_TEMPLATE_IDS",
        "UNKNOWN_TEMPLATE_IDS",
    }


def test_missing_required_field_has_json_location(tmp_path: Path) -> None:
    request = write_package(tmp_path, [{"题号": "Q1"}], ["Q1"])
    with pytest.raises(InputFormatError) as caught:
        execute(request, tmp_path)
    assert caught.value.location.json_path == "$[0].自然语言输入"
