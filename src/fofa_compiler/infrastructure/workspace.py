from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from fofa_compiler.domain.errors import (
    AtomicWriteError,
    ErrorLocation,
    WorkspaceCorruptedError,
)

T = TypeVar("T", bound=BaseModel)


class JsonWorkspaceRepository:
    """Versioned JSON repository with deterministic, atomic replacement."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def _resolve(self, relative_path: str) -> Path:
        candidate = (self._root / relative_path).resolve()
        if candidate == self._root or self._root not in candidate.parents:
            raise WorkspaceCorruptedError(
                "工作区路径越界",
                location=ErrorLocation(file=relative_path),
            )
        return candidate

    def save_model(self, relative_path: str, model: BaseModel) -> None:
        self.save_json(relative_path, model.model_dump(mode="json", by_alias=True))

    def load_model(self, relative_path: str, model_type: type[T]) -> T:
        value = self.load_json(relative_path)
        try:
            return model_type.model_validate(value)
        except ValidationError as exc:
            raise WorkspaceCorruptedError(
                "工作区数据不符合模型定义",
                location=ErrorLocation(file=relative_path),
                details=[{"validation": error} for error in exc.errors(include_url=False)],
            ) from exc

    def save_json(self, relative_path: str, value: Any) -> None:
        target = self._resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8") + b"\n"
        temporary_path: Path | None = None
        try:
            descriptor, raw_path = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
            temporary_path = Path(raw_path)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, target)
            temporary_path = None
            directory_fd = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except (OSError, TypeError, ValueError) as exc:
            raise AtomicWriteError(
                "无法原子写入工作区文件",
                location=ErrorLocation(file=relative_path),
            ) from exc
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def load_json(self, relative_path: str) -> Any:
        target = self._resolve(relative_path)
        try:
            return json.loads(target.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise WorkspaceCorruptedError(
                "无法读取工作区 JSON 文件",
                location=ErrorLocation(file=relative_path),
            ) from exc
