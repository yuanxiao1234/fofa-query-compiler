from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from fastapi import Request

from fofa_compiler.application.container import ApplicationContainer
from fofa_compiler.domain.models import CompetitionPackage


def container(request: Request) -> ApplicationContainer:
    return cast(ApplicationContainer, request.app.state.container)


def package_or_none(request: Request) -> CompetitionPackage | None:
    repository = container(request).workspace
    if not (repository.root / "package.json").is_file():
        return None
    return repository.load_model("package.json", CompetitionPackage)


def relative_json_paths(root: Path, pattern: str) -> list[str]:
    return [str(path.relative_to(root)) for path in sorted(root.glob(pattern))]


def model_json(value: Any) -> Any:
    return value.model_dump(mode="json") if value is not None else None
