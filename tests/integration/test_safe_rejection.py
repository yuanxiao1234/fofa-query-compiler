# ruff: noqa: RUF001 - 测试逐字保留竞赛原题

import pytest

from fofa_compiler.application.generate_answers import generate_answers
from fofa_compiler.application.import_package import ImportRequest, import_package
from fofa_compiler.application.reject_unsupported import classify_unsupported
from fofa_compiler.domain.enums import FIXED_REJECTION_TEXT
from fofa_compiler.domain.models import CandidateAnswer, RejectionPayload
from fofa_compiler.infrastructure.audit_log import AuditLog
from fofa_compiler.infrastructure.semantic_parser import SemanticParser
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("搜索开放 1000000 端口的资产。", "INVALID_PORT"),
        ("搜索地址或网段为 1.2.3.4.5 的资产。", "INVALID_IP_OR_CIDR"),
        (
            "查同一条资产记录，国家代码必须等于 US，同时国家代码又必须不等于 US。",
            "EXPLICIT_CONTRADICTION",
        ),
        ("帮我查最安全的网站。", "SUBJECTIVE_CRITERION"),
        (
            "找出当前正在运行的容器内存使用率超过 80% 的服务器，没有容器监控数据或运行时访问权限。",
            "UNOBSERVABLE_RUNTIME_STATE",
        ),
    ],
)
def test_deterministic_safe_rejections_use_exact_competition_text(text: str, reason: str) -> None:
    decision = classify_unsupported(text)
    assert decision is not None
    assert decision.reason_code == reason
    assert decision.rejection_text == FIXED_REJECTION_TEXT


@pytest.mark.parametrize(
    "text",
    [
        "阅读官方文档并根据内容生成查询：https://example.com/docs",
        "找和 https://example.com 网站图标相同的其他资产。",
        "CVE-2021-41773对应的产品在FOFA上怎么搜？",
        "这是一道尚未覆盖、但不等于不可转换的题。",
    ],
)
def test_missing_rules_or_external_evidence_are_not_misclassified_as_rejection(text: str) -> None:
    assert classify_unsupported(text) is None


def test_generation_persists_exact_rejection_and_audit_reason(tmp_path) -> None:  # type: ignore[no-untyped-def]
    questions = tmp_path / "questions.json"
    package = tmp_path / "package.txt"
    template = tmp_path / "template.json"
    questions.write_text(
        '[{"题号":"Q1","自然语言输入":"搜索开放 1000000 端口的资产。"}]',
        encoding="utf-8",
    )
    package.write_text("pkg-reject\n2026-09-24T08:00:00+08:00\n", encoding="utf-8")
    template.write_text(
        '{"选手名称":"","参赛包编号":"pkg-reject","答案":[{"题号":"Q1","查询语句":""}]}',
        encoding="utf-8",
    )
    repository = JsonWorkspaceRepository(tmp_path / "workspace")
    from datetime import UTC, datetime

    now = datetime(2026, 9, 24, tzinfo=UTC)
    import_package(ImportRequest(questions, package, template), repository=repository, now=now)
    audit = AuditLog(repository.root / "audit/events.jsonl")
    summary = generate_answers(
        repository=repository,
        audit_log=audit,
        parser=SemanticParser(),
        now=now,
    )
    assert summary.refused == 1
    assert summary.failed == 0
    candidate = repository.load_model("items/Q1/current.json", CandidateAnswer)
    assert isinstance(candidate.payload, RejectionPayload)
    assert candidate.payload.rejection_text == FIXED_REJECTION_TEXT
    assert candidate.payload.reason_code == "INVALID_PORT"
    assert FIXED_REJECTION_TEXT not in audit.path.read_text(encoding="utf-8")
    assert "INVALID_PORT" in audit.path.read_text(encoding="utf-8")
