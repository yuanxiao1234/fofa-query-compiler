import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fofa_compiler.application.generate_answers import generate_answers
from fofa_compiler.application.import_package import ImportRequest, import_package
from fofa_compiler.infrastructure.audit_log import AuditLog
from fofa_compiler.infrastructure.semantic_parser import SemanticParser
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository


@dataclass(frozen=True)
class FixedClock:
    value: datetime

    def now(self) -> datetime:
        return self.value


def prepare_workspace(tmp_path: Path) -> tuple[JsonWorkspaceRepository, AuditLog, datetime]:
    questions = tmp_path / "questions.json"
    package_file = tmp_path / "package.txt"
    template = tmp_path / "template.json"
    questions.write_text(
        json.dumps(
            [
                {"题号": "Q1", "自然语言输入": "请查询 IP 地址为 20.247.40.92 的资产。"},
                {"题号": "Q2", "自然语言输入": "这是一个尚未支持的复杂题目。"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    package_file.write_text("pkg-determinism\n2026-09-24T08:00:00+08:00\n", encoding="utf-8")
    template.write_text(
        json.dumps(
            {
                "选手名称": "",
                "参赛包编号": "pkg-determinism",
                "答案": [
                    {"题号": "Q1", "查询语句": ""},
                    {"题号": "Q2", "查询语句": ""},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    now = datetime(2026, 9, 24, tzinfo=UTC)
    repository = JsonWorkspaceRepository(tmp_path / "workspace")
    import_package(
        ImportRequest(questions, package_file, template), repository=repository, now=now
    )
    return repository, AuditLog(repository.root / "audit" / "events.jsonl"), now


def test_three_runs_produce_identical_ir_query_and_audit_state(tmp_path: Path) -> None:
    repository, audit_log, now = prepare_workspace(tmp_path)
    snapshots: list[tuple[bytes, bytes, bytes]] = []
    for _ in range(3):
        summary = generate_answers(
            repository=repository,
            audit_log=audit_log,
            parser=SemanticParser(),
            now=now,
        )
        assert summary.generated == 1
        assert summary.failed == 1
        snapshots.append(
            (
                (repository.root / "items/Q1/current.json").read_bytes(),
                (repository.root / "items/Q1/intent.json").read_bytes(),
                audit_log.path.read_bytes(),
            )
        )
    assert snapshots[0] == snapshots[1] == snapshots[2]


def test_single_question_generation_does_not_touch_other_items(tmp_path: Path) -> None:
    repository, audit_log, now = prepare_workspace(tmp_path)
    summary = generate_answers(
        repository=repository,
        audit_log=audit_log,
        parser=SemanticParser(),
        now=now,
        question_id="Q1",
    )
    assert summary.status == "completed"
    assert summary.items[0].query == 'ip="20.247.40.92"'
    assert not (repository.root / "items/Q2").exists()

