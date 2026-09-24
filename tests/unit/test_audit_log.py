import json
from datetime import UTC, datetime

from fofa_compiler.infrastructure.audit_log import AuditLog


def test_audit_log_redacts_sensitive_nested_values(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "audit" / "events.jsonl"
    AuditLog(path).append(
        event_type="candidate.created",
        occurred_at=datetime(2026, 9, 24, tzinfo=UTC),
        actor="local-user",
        data={"question_id": "M001-S009", "nested": {"api_key": "do-not-store"}},
    )
    event = json.loads(path.read_text(encoding="utf-8"))
    assert event["data"]["nested"]["api_key"] == "[REDACTED]"
    assert "do-not-store" not in path.read_text(encoding="utf-8")
