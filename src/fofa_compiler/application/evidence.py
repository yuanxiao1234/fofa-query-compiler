from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from fofa_compiler.domain.enums import EvidenceAccessStatus, EvidenceSourceKind
from fofa_compiler.domain.errors import ErrorLocation, ValidationError
from fofa_compiler.domain.models import CompetitionPackage, EvidenceFact, EvidenceRecord
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository


@dataclass(frozen=True, slots=True)
class EvidenceInput:
    question_id: str
    source_kind: EvidenceSourceKind
    source_locator: str
    facts: tuple[str, ...]
    content: bytes | None
    verified_by: str | None
    access_status: EvidenceAccessStatus = EvidenceAccessStatus.ACCESSIBLE
    original_source_locator: str | None = None
    equivalence_assessment: dict[str, object] | None = None


def add_evidence(
    repository: JsonWorkspaceRepository, request: EvidenceInput, *, now: datetime
) -> EvidenceRecord:
    package = repository.load_model("package.json", CompetitionPackage)
    if request.question_id not in package.original_order:
        raise ValidationError("题号不存在", location=ErrorLocation(question_id=request.question_id))
    locator = request.source_locator.strip()
    verifier = request.verified_by.strip() if request.verified_by else None
    if not locator:
        raise ValidationError("证据来源不能为空")
    replacement_kinds = {
        EvidenceSourceKind.OFFICIAL_ALTERNATIVE,
        EvidenceSourceKind.VERIFIED_ARCHIVE,
    }
    if request.source_kind in replacement_kinds and (
        not request.original_source_locator
        or not request.equivalence_assessment
        or request.equivalence_assessment.get("equivalent") is not True
    ):
        raise ValidationError("替代或存档来源必须记录原始来源并确认等价性")

    accessible = request.access_status is EvidenceAccessStatus.ACCESSIBLE
    digest = hashlib.sha256(request.content).hexdigest() if request.content is not None else None
    sufficient = bool(accessible and digest and request.facts and verifier)
    seed = "\0".join(
        (
            request.question_id,
            request.source_kind.value,
            locator,
            digest or "",
            *request.facts,
        )
    )
    evidence_id = "evidence-" + hashlib.sha256(seed.encode()).hexdigest()[:20]
    record = EvidenceRecord(
        evidence_id=evidence_id,
        question_id=request.question_id,
        source_kind=request.source_kind,
        source_locator=locator,
        original_source_locator=request.original_source_locator,
        retrieved_at=now if accessible else None,
        content_digest=digest,
        access_status=request.access_status,
        extracted_facts=tuple(
            EvidenceFact(name=f"fact-{index}", value=fact)
            for index, fact in enumerate(request.facts, 1)
        ),
        equivalence_assessment=request.equivalence_assessment,
        verified_by=verifier,
        verified_at=now if verifier and accessible else None,
        is_sufficient=sufficient,
    )
    repository.save_model(f"evidence/{request.question_id}/{record.evidence_id}.json", record)
    return record
