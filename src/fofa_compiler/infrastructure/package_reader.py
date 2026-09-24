from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from fofa_compiler.domain.errors import ErrorLocation, InputFormatError

PACKAGE_ID_PATTERN = re.compile(r"pkg-[A-Za-z0-9_-]+")


@dataclass(frozen=True, slots=True)
class SourceDocument:
    path: Path
    content: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


@dataclass(frozen=True, slots=True)
class PackageMetadata:
    package_id: str
    issued_at: datetime | None


def read_source(path: Path) -> SourceDocument:
    try:
        return SourceDocument(path=path, content=path.read_bytes())
    except OSError as exc:
        raise InputFormatError(
            "无法读取输入文件", location=ErrorLocation(file=str(path))
        ) from exc


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    duplicates: list[str] = []
    for key, value in pairs:
        if key in result:
            duplicates.append(key)
        result[key] = value
    if duplicates:
        raise ValueError(f"重复 JSON 键: {', '.join(sorted(set(duplicates)))}")
    return result


def read_json(document: SourceDocument) -> Any:
    try:
        text = document.content.decode("utf-8-sig")
        return json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise InputFormatError(
            f"输入不是合法 JSON: {exc}",
            location=ErrorLocation(file=str(document.path)),
        ) from exc


def read_package_metadata(document: SourceDocument) -> PackageMetadata:
    try:
        text = document.content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InputFormatError(
            "参赛包信息不是 UTF-8 文本", location=ErrorLocation(file=str(document.path))
        ) from exc
    match = PACKAGE_ID_PATTERN.search(text)
    if match is None:
        raise InputFormatError(
            "参赛包信息中缺少有效包编号",
            location=ErrorLocation(file=str(document.path)),
        )
    issued_at = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line == match.group(0):
            continue
        try:
            parsed = datetime.fromisoformat(line)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            raise InputFormatError(
                "参赛包发放时间必须包含时区",
                location=ErrorLocation(file=str(document.path)),
            )
        issued_at = parsed
        break
    return PackageMetadata(package_id=match.group(0), issued_at=issued_at)
