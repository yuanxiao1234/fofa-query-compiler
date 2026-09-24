from __future__ import annotations

from pathlib import Path

import pytest
from tests.export_helpers import NOW, seed_exportable_workspace

from fofa_compiler.application.evidence import EvidenceInput, add_evidence
from fofa_compiler.domain.enums import EvidenceAccessStatus, EvidenceSourceKind
from fofa_compiler.domain.errors import ValidationError
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository


def test_primary_and_user_material_are_sufficient_only_after_verification(tmp_path: Path) -> None:
    repository = JsonWorkspaceRepository(tmp_path / "workspace")
    seed_exportable_workspace(repository, 1)

    record = add_evidence(
        repository,
        EvidenceInput(
            "Q001",
            EvidenceSourceKind.OFFICIAL_PRIMARY,
            "https://example.test/doc",
            ("field",),
            b"source",
            "reviewer",
        ),
        now=NOW,
    )
    user_record = add_evidence(
        repository,
        EvidenceInput(
            "Q001",
            EvidenceSourceKind.USER_PROVIDED,
            "material-1",
            ("fact",),
            b"material",
            "reviewer",
        ),
        now=NOW,
    )

    assert record.is_sufficient and user_record.is_sufficient


def test_alternative_requires_original_and_equivalence_and_unavailable_is_blocked(
    tmp_path: Path,
) -> None:
    repository = JsonWorkspaceRepository(tmp_path / "workspace")
    seed_exportable_workspace(repository, 1)

    with pytest.raises(ValidationError):
        add_evidence(
            repository,
            EvidenceInput(
                "Q001",
                EvidenceSourceKind.OFFICIAL_ALTERNATIVE,
                "https://alt.test",
                ("fact",),
                b"alt",
                "reviewer",
            ),
            now=NOW,
        )
    alternative = add_evidence(
        repository,
        EvidenceInput(
            "Q001",
            EvidenceSourceKind.VERIFIED_ARCHIVE,
            "https://archive.test",
            ("fact",),
            b"archive",
            "reviewer",
            original_source_locator="https://original.test",
            equivalence_assessment={"equivalent": True},
        ),
        now=NOW,
    )
    unavailable = add_evidence(
        repository,
        EvidenceInput(
            "Q001",
            EvidenceSourceKind.OFFICIAL_PRIMARY,
            "https://down.test",
            (),
            None,
            None,
            access_status=EvidenceAccessStatus.UNAVAILABLE,
        ),
        now=NOW,
    )

    assert alternative.is_sufficient
    assert not unavailable.is_sufficient
