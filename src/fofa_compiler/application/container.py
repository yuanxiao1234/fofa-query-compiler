from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fofa_compiler.application.ports import Clock
from fofa_compiler.infrastructure.audit_log import AuditLog
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ApplicationContainer:
    workspace: JsonWorkspaceRepository
    audit_log: AuditLog
    clock: Clock


def build_container(workspace_root: Path, *, clock: Clock | None = None) -> ApplicationContainer:
    workspace = JsonWorkspaceRepository(workspace_root)
    return ApplicationContainer(
        workspace=workspace,
        audit_log=AuditLog(workspace.root / "audit" / "events.jsonl"),
        clock=clock or SystemClock(),
    )
