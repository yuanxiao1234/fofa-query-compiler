from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ErrorLocation:
    file: str | None = None
    json_path: str | None = None
    question_id: str | None = None


class FofaCompilerError(Exception):
    code = "FOFA_COMPILER_ERROR"

    def __init__(
        self,
        message: str,
        *,
        location: ErrorLocation | None = None,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.location = location or ErrorLocation()
        self.details = details or []


class InputFormatError(FofaCompilerError):
    code = "INPUT_FORMAT_ERROR"


class PackageIntegrityError(FofaCompilerError):
    code = "PACKAGE_INTEGRITY_ERROR"


class WorkspaceError(FofaCompilerError):
    code = "WORKSPACE_ERROR"


class WorkspaceCorruptedError(WorkspaceError):
    code = "WORKSPACE_CORRUPTED"


class WorkspaceVersionError(WorkspaceError):
    code = "WORKSPACE_VERSION_UNSUPPORTED"


class AtomicWriteError(WorkspaceError):
    code = "ATOMIC_WRITE_ERROR"


class StaleRevisionError(WorkspaceError):
    code = "STALE_REVISION"


class ValidationError(FofaCompilerError):
    code = "VALIDATION_ERROR"


class ExportBlockedError(FofaCompilerError):
    code = "EXPORT_BLOCKED"
