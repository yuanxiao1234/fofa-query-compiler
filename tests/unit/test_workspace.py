from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from fofa_compiler.domain.enums import FindingSeverity
from fofa_compiler.domain.errors import AtomicWriteError, WorkspaceCorruptedError
from fofa_compiler.domain.models import Finding, ValidationReport
from fofa_compiler.infrastructure import workspace as workspace_module
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository


def sample_report() -> ValidationReport:
    return ValidationReport(
        report_id="report-1",
        validator_version="1",
        is_valid=True,
        validated_at=datetime(2026, 9, 24, tzinfo=UTC),
        input_checks=(
            Finding(
                code="INPUT_OK",
                severity=FindingSeverity.INFO,
                message="输入有效",
            ),
        ),
    )


def test_domain_model_round_trip_and_unknown_fields_rejected() -> None:
    report = sample_report()
    restored = ValidationReport.model_validate_json(report.model_dump_json())
    assert restored == report
    with pytest.raises(ValidationError):
        ValidationReport.model_validate({**report.model_dump(), "unexpected": True})


def test_workspace_can_be_reopened(workspace_factory) -> None:  # type: ignore[no-untyped-def]
    root = workspace_factory()
    JsonWorkspaceRepository(root).save_model("state/report.json", sample_report())

    reopened = JsonWorkspaceRepository(root)
    assert reopened.load_model("state/report.json", ValidationReport) == sample_report()
    raw = (root / "state/report.json").read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert "输入有效" in raw


def test_corrupt_workspace_file_is_reported(workspace_factory) -> None:  # type: ignore[no-untyped-def]
    root = workspace_factory()
    target = root / "state.json"
    target.write_text("not-json", encoding="utf-8")

    with pytest.raises(WorkspaceCorruptedError):
        JsonWorkspaceRepository(root).load_json("state.json")


def test_failed_atomic_replace_preserves_previous_file(
    workspace_factory, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    root = workspace_factory()
    repository = JsonWorkspaceRepository(root)
    repository.save_json("state.json", {"revision": 1})

    def fail_replace(source: Path, target: Path) -> None:
        raise OSError("simulated failure")

    monkeypatch.setattr(workspace_module.os, "replace", fail_replace)
    with pytest.raises(AtomicWriteError):
        repository.save_json("state.json", {"revision": 2})

    assert json.loads((root / "state.json").read_text(encoding="utf-8")) == {"revision": 1}


def test_workspace_rejects_path_escape(workspace_factory) -> None:  # type: ignore[no-untyped-def]
    repository = JsonWorkspaceRepository(workspace_factory())
    with pytest.raises(WorkspaceCorruptedError):
        repository.save_json("../outside.json", {})
