from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from fofa_compiler.domain.errors import ValidationError
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository


@dataclass(frozen=True, slots=True)
class AtomicJudgement:
    constraint: str
    passed: bool


@dataclass(frozen=True, slots=True)
class SemanticJudgement:
    judgement_id: str
    question_id: str
    candidate_revision: int
    reviewer: str
    checks: tuple[AtomicJudgement, ...]
    passed: bool
    judged_at: datetime


@dataclass(frozen=True, slots=True)
class AcceptanceResult:
    accepted: bool
    adjudicated: bool
    disagreements: tuple[str, ...]


def record_judgement(
    repository: JsonWorkspaceRepository,
    question_id: str,
    candidate_revision: int,
    reviewer: str,
    checks: tuple[AtomicJudgement, ...],
    *,
    now: datetime,
) -> SemanticJudgement:
    if not reviewer.strip() or not checks:
        raise ValidationError("复核者和原子约束判定不能为空")
    if len({item.constraint for item in checks}) != len(checks):
        raise ValidationError("同一复核记录不能重复原子约束")
    seed = f"{question_id}\0{candidate_revision}\0{reviewer.strip()}"
    judgement = SemanticJudgement(
        judgement_id="judgement-" + hashlib.sha256(seed.encode()).hexdigest()[:20],
        question_id=question_id,
        candidate_revision=candidate_revision,
        reviewer=reviewer.strip(),
        checks=checks,
        passed=all(item.passed for item in checks),
        judged_at=now,
    )
    repository.save_json(
        f"benchmarks/{question_id}/{candidate_revision}/{judgement.judgement_id}.json",
        {
            "judgement_id": judgement.judgement_id,
            "question_id": judgement.question_id,
            "candidate_revision": judgement.candidate_revision,
            "reviewer": judgement.reviewer,
            "checks": [
                {"constraint": item.constraint, "passed": item.passed} for item in judgement.checks
            ],
            "passed": judgement.passed,
            "judged_at": judgement.judged_at.isoformat(),
        },
    )
    return judgement


def resolve_acceptance(
    repository: JsonWorkspaceRepository,
    question_id: str,
    candidate_revision: int,
    *,
    adjudicator: str | None = None,
    adjudicated_pass: bool | None = None,
    now: datetime | None = None,
) -> AcceptanceResult:
    root = repository.root / "benchmarks" / question_id / str(candidate_revision)
    records = (
        []
        if not root.is_dir()
        else [
            repository.load_json(str(path.relative_to(repository.root)))
            for path in sorted(root.glob("judgement-*.json"))
        ]
    )
    reviewers = {record["reviewer"] for record in records}
    if len(reviewers) < 2:
        return AcceptanceResult(False, False, ("TWO_INDEPENDENT_REVIEWERS_REQUIRED",))
    by_constraint: dict[str, set[bool]] = {}
    for record in records:
        for check in record["checks"]:
            by_constraint.setdefault(check["constraint"], set()).add(check["passed"])
    disagreements = tuple(sorted(key for key, values in by_constraint.items() if len(values) > 1))
    if disagreements:
        if not adjudicator or adjudicated_pass is None or now is None:
            return AcceptanceResult(False, False, disagreements)
        repository.save_json(
            f"benchmarks/{question_id}/{candidate_revision}/adjudication.json",
            {
                "adjudicator": adjudicator,
                "passed": adjudicated_pass,
                "resolved_at": now.isoformat(),
                "disagreements": disagreements,
            },
        )
        return AcceptanceResult(adjudicated_pass, True, ())
    return AcceptanceResult(all(record["passed"] for record in records), False, ())
