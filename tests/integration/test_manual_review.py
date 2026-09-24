from __future__ import annotations

from pathlib import Path

import pytest
from tests.export_helpers import NOW, seed_exportable_workspace

from fofa_compiler.application.review_answer import amend_answer, confirm_answer
from fofa_compiler.application.semantic_acceptance import (
    AtomicJudgement,
    record_judgement,
    resolve_acceptance,
)
from fofa_compiler.cli import main
from fofa_compiler.domain.enums import RiskLevel
from fofa_compiler.domain.errors import ValidationError
from fofa_compiler.domain.models import CandidateAnswer, FinalAnswer, RiskAssessment, RiskItem
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository


def test_amendment_creates_revision_and_invalidates_old_final_answer(tmp_path: Path) -> None:
    repository = JsonWorkspaceRepository(tmp_path / "workspace")
    seed_exportable_workspace(repository, 1)

    amended = amend_answer(
        repository, "Q001", "该需求不能直接转换为FOFA搜索语句", reviewer="alice", now=NOW
    )

    assert amended.revision == 2
    assert not (repository.root / "items/Q001/final-answer.json").exists()
    with pytest.raises(ValidationError):
        confirm_answer(
            repository,
            "Q001",
            reviewer="alice",
            checked_risk_item_ids=(),
            reviewed_evidence_ids=(),
            now=NOW,
        )


def test_high_risk_confirmation_requires_and_records_every_check(tmp_path: Path) -> None:
    repository = JsonWorkspaceRepository(tmp_path / "workspace")
    seed_exportable_workspace(repository, 1)
    risk = repository.load_model("items/Q001/risks.json", RiskAssessment)
    repository.save_model(
        "items/Q001/risks.json",
        risk.model_copy(
            update={
                "risk_level": RiskLevel.HIGH,
                "risk_items": (RiskItem(item_id="r1", code="REGEX", description="检查"),),
            }
        ),
    )
    with pytest.raises(ValidationError):
        confirm_answer(
            repository,
            "Q001",
            reviewer="alice",
            checked_risk_item_ids=(),
            reviewed_evidence_ids=(),
            now=NOW,
        )

    final = confirm_answer(
        repository,
        "Q001",
        reviewer="alice",
        checked_risk_item_ids=("r1",),
        reviewed_evidence_ids=(),
        now=NOW,
    )

    assert isinstance(final, FinalAnswer)
    resolved = repository.load_model("items/Q001/risks.json", RiskAssessment)
    assert resolved.risk_items[0].resolved


def test_two_reviewer_disagreement_requires_adjudication(tmp_path: Path) -> None:
    repository = JsonWorkspaceRepository(tmp_path / "workspace")
    seed_exportable_workspace(repository, 1)
    candidate = repository.load_model("items/Q001/current.json", CandidateAnswer)
    record_judgement(
        repository, "Q001", candidate.revision, "alice", (AtomicJudgement("field", True),), now=NOW
    )
    record_judgement(
        repository, "Q001", candidate.revision, "bob", (AtomicJudgement("field", False),), now=NOW
    )

    assert not resolve_acceptance(repository, "Q001", candidate.revision).accepted
    resolved = resolve_acceptance(
        repository, "Q001", candidate.revision, adjudicator="carol", adjudicated_pass=True, now=NOW
    )
    assert resolved.accepted and resolved.adjudicated


def test_review_and_evidence_cli_commands(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = JsonWorkspaceRepository(tmp_path / "workspace")
    seed_exportable_workspace(repository, 2)
    content = tmp_path / "evidence.txt"
    content.write_text("official field definition", encoding="utf-8")

    assert (
        main(["review", "show", "--workspace", str(repository.root), "--question-id", "Q001"]) == 0
    )
    assert (
        main(
            [
                "review",
                "confirm",
                "--workspace",
                str(repository.root),
                "--question-id",
                "Q001",
                "--reviewer",
                "alice",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "review",
                "amend",
                "--workspace",
                str(repository.root),
                "--question-id",
                "Q002",
                "--reviewer",
                "alice",
                "--query",
                "该需求不能直接转换为FOFA搜索语句",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "evidence",
                "add",
                "--workspace",
                str(repository.root),
                "--question-id",
                "Q001",
                "--source",
                "https://example.test",
                "--kind",
                "official_primary",
                "--fact",
                "field",
                "--content-file",
                str(content),
                "--verified-by",
                "alice",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert '"question_id":"Q001"' in output
    assert '"is_sufficient":true' in output
