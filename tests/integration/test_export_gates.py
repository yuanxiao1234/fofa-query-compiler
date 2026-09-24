from __future__ import annotations

from pathlib import Path

import pytest
from tests.export_helpers import seed_exportable_workspace

from fofa_compiler.application.export_answers import export_answers
from fofa_compiler.application.export_gates import preflight_export
from fofa_compiler.cli import main
from fofa_compiler.domain.enums import RiskLevel
from fofa_compiler.domain.errors import ExportBlockedError
from fofa_compiler.domain.models import FinalAnswer, RiskAssessment, RiskItem
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository


def test_export_gate_aggregates_empty_id_confirmation_risk_and_evidence_blockers(
    tmp_path: Path,
) -> None:
    repository = JsonWorkspaceRepository(tmp_path / "workspace")
    seed_exportable_workspace(repository, 3)

    first = repository.load_model("items/Q001/final-answer.json", FinalAnswer)
    repository.save_model(
        "items/Q001/final-answer.json", first.model_copy(update={"query_text": "   "})
    )
    (repository.root / "items/Q002/final-answer.json").unlink()
    risk = repository.load_model("items/Q003/risks.json", RiskAssessment)
    repository.save_model(
        "items/Q003/risks.json",
        risk.model_copy(
            update={
                "risk_level": RiskLevel.HIGH,
                "requires_evidence_review": True,
                "risk_items": (RiskItem(item_id="risk-1", code="REGEX", description="核对正则"),),
            }
        ),
    )
    (repository.root / "items/Q003/reviews/review-Q003.json").unlink()
    repository.save_json(
        "items/UNKNOWN/final-answer.json",
        first.model_copy(update={"question_id": "UNKNOWN"}).model_dump(mode="json"),
    )

    report = preflight_export(repository)

    assert not report.ready
    assert {blocker.code for blocker in report.blockers} >= {
        "EMPTY_ANSWER",
        "MISSING_FINAL_ANSWER",
        "UNKNOWN_FINAL_ANSWER_ID",
        "MISSING_CONFIRMATION",
        "INCOMPLETE_HIGH_RISK_CHECKS",
        "INSUFFICIENT_EVIDENCE",
    }


def test_failed_preflight_neither_creates_nor_overwrites_output(tmp_path: Path) -> None:
    repository = JsonWorkspaceRepository(tmp_path / "workspace")
    seed_exportable_workspace(repository, 2)
    (repository.root / "items/Q002/final-answer.json").unlink()
    new_target = tmp_path / "new.json"
    existing_target = tmp_path / "existing.json"
    existing_target.write_bytes(b"keep-me")

    with pytest.raises(ExportBlockedError):
        export_answers(repository, participant_name="选手", output_path=new_target)
    with pytest.raises(ExportBlockedError):
        export_answers(repository, participant_name="选手", output_path=existing_target)

    assert not new_target.exists()
    assert existing_target.read_bytes() == b"keep-me"


def test_export_cli_reports_every_preflight_blocker(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = JsonWorkspaceRepository(tmp_path / "workspace")
    seed_exportable_workspace(repository, 2)
    (repository.root / "items/Q001/final-answer.json").unlink()
    (repository.root / "items/Q002/reviews/review-Q002.json").unlink()

    exit_code = main(
        [
            "export",
            "--workspace",
            str(repository.root),
            "--participant",
            "选手",
            "--output",
            str(tmp_path / "answer.json"),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 9
    assert "MISSING_FINAL_ANSWER" in output
    assert "MISSING_CONFIRMATION" in output
    assert not (tmp_path / "answer.json").exists()
