from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient
from tests.export_helpers import seed_exportable_workspace

from fofa_compiler.cli import main
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository
from fofa_compiler.web.app import create_app


def _client(tmp_path: Path) -> tuple[TestClient, Path]:
    workspace = tmp_path / "workspace"
    seed_exportable_workspace(JsonWorkspaceRepository(workspace), 3)
    return TestClient(create_app(workspace)), workspace


def _csrf(client: TestClient) -> dict[str, str]:
    token = client.get("/api/v1/status").json()["csrf_token"]
    return {"X-CSRF-Token": token, "Origin": "http://testserver"}


def test_health_pages_security_headers_status_and_filters(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)

    health = client.get("/health")
    assert health.json() == {"status": "ok"}
    assert health.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in health.headers["content-security-policy"]
    assert "HttpOnly" in health.headers["set-cookie"]
    assert "FOFA 查询编译器" in client.get("/").text
    assert client.get("/import").status_code == 200
    assert client.get("/questions").status_code == 200
    assert client.get("/questions/Q001").status_code == 200
    filtered = client.get("/api/v1/questions", params={"risk": "low", "question_id": "Q002"})
    assert [item["question_id"] for item in filtered.json()["items"]] == ["Q002"]


def test_revision_conflict_review_evidence_and_export_preflight(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    headers = _csrf(client)

    conflict = client.put(
        "/api/v1/questions/Q001/answer",
        json={
            "query": "该需求不能直接转换为FOFA搜索语句",
            "reviewer": "alice",
            "expected_revision": 99,
        },
        headers=headers,
    )
    assert conflict.status_code == 409
    amended = client.put(
        "/api/v1/questions/Q001/answer",
        json={
            "query": "该需求不能直接转换为FOFA搜索语句",
            "reviewer": "alice",
            "expected_revision": 1,
        },
        headers=headers,
    )
    assert amended.json()["revision"] == 2
    risk_id = client.get("/api/v1/questions/Q001").json()["risk"]["risk_items"][0]["item_id"]
    confirmed = client.post(
        "/api/v1/questions/Q001/confirm",
        json={
            "reviewer": "alice",
            "expected_revision": 2,
            "risk_item_ids": [risk_id],
            "evidence_ids": [],
        },
        headers=headers,
    )
    assert confirmed.status_code == 200

    evidence = client.post(
        "/api/v1/questions/Q001/evidence",
        json={
            "source": "material-1",
            "kind": "user_provided",
            "facts": ["fact"],
            "content": "source",
            "verified_by": "alice",
        },
        headers=headers,
    )
    assert evidence.json()["is_sufficient"] is True
    preflight = client.get("/export")
    assert "导出答卷" in preflight.text


def test_csrf_and_host_validation_reject_unsafe_requests(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    assert client.post("/api/v1/generation-jobs").status_code == 403
    assert client.get("/health", headers={"Host": "evil.example"}).status_code == 400
    assert main(["web", "--workspace", str(tmp_path), "--host", "0.0.0.0"]) == 3


def test_web_import_and_generation_job_preserve_successful_results(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    client = TestClient(create_app(workspace))
    headers = _csrf(client)
    question_id = "M001-S009"
    questions = json.dumps(
        [
            {"题号": question_id, "自然语言输入": "请查询 IP 地址为 20.247.40.92 的资产。"},
            {"题号": "Q-FAILED", "自然语言输入": "尚未支持的完整新语义。"},
        ],
        ensure_ascii=False,
    ).encode()
    template = json.dumps(
        {
            "选手名称": "",
            "参赛包编号": "pkg-web",
            "答案": [
                {"题号": question_id, "查询语句": ""},
                {"题号": "Q-FAILED", "查询语句": ""},
            ],
        },
        ensure_ascii=False,
    ).encode()

    imported = client.post(
        "/api/v1/import",
        files={
            "questions": ("questions.json", questions, "application/json"),
            "package": ("package.txt", b"pkg-web", "text/plain"),
            "template": ("template.json", template, "application/json"),
        },
        headers=headers,
    )
    generated = client.post("/api/v1/generation-jobs", headers=headers)

    assert imported.json() == {"package_id": "pkg-web", "total": 2}
    job_id = generated.json()["job_id"]
    job = generated.json()
    for _ in range(100):
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        if job["status"] not in {"queued", "running"}:
            break
        time.sleep(0.01)
    assert job["generated"] == 1
    assert job["failed"] == 1
    assert job["status"] == "completed_with_errors"
