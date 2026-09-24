from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class Clock(Protocol):
    def now(self) -> datetime: ...


class CandidateGenerator(Protocol):
    def generate(self, question_id: str, raw_text: str) -> Any: ...


class EvidenceReader(Protocol):
    def read(self, locator: str) -> bytes: ...


class WorkspaceRepository(Protocol):
    @property
    def root(self) -> Path: ...

    def save_model(self, relative_path: str, model: BaseModel) -> None: ...

    def load_model(self, relative_path: str, model_type: type[T]) -> T: ...

    def save_json(self, relative_path: str, value: Any) -> None: ...

    def load_json(self, relative_path: str) -> Any: ...
