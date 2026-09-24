from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.export_helpers import seed_exportable_workspace

from fofa_compiler.application.export_answers import export_answers
from fofa_compiler.domain.errors import ExportBlockedError
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository


def test_exports_100_answers_in_source_order_as_deterministic_clean_utf8_json(
    tmp_path: Path,
) -> None:
    repository = JsonWorkspaceRepository(tmp_path / "workspace")
    package = seed_exportable_workspace(repository, 100)
    first_path = tmp_path / "answer-a.json"
    second_path = tmp_path / "answer-b.json"

    first = export_answers(repository, participant_name="测试选手", output_path=first_path)
    second = export_answers(repository, participant_name="测试选手", output_path=second_path)

    assert first.answer_count == second.answer_count == 100
    assert first_path.read_bytes() == second_path.read_bytes()
    assert "测试选手" in first_path.read_text(encoding="utf-8")
    document = json.loads(first_path.read_bytes())
    assert set(document) == {"选手名称", "参赛包编号", "答案"}
    assert document["参赛包编号"] == package.package_id
    assert [item["题号"] for item in document["答案"]] == list(package.original_order)
    assert all(set(item) == {"题号", "查询语句"} for item in document["答案"])
    assert first.byte_size < 8 * 1024 * 1024

    with pytest.raises(ExportBlockedError, match="已存在"):
        export_answers(repository, participant_name="测试选手", output_path=first_path)
