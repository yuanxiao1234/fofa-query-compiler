from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from tests.export_helpers import seed_exportable_workspace

from fofa_compiler.application.export_answers import export_answers
from fofa_compiler.infrastructure.workspace import JsonWorkspaceRepository
from fofa_compiler.web.app import create_app


def test_web_state_survives_restart_and_export_matches_shared_cli_service(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    repository = JsonWorkspaceRepository(workspace)
    seed_exportable_workspace(repository, 100)
    first_client = TestClient(create_app(workspace))
    first_status = first_client.get("/api/v1/status").json()

    second_client = TestClient(create_app(workspace))
    second_status = second_client.get("/api/v1/status").json()
    token = second_status["csrf_token"]
    web_response = second_client.post(
        "/api/v1/export",
        json={"participant": "测试选手"},
        headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
    )
    cli_path = tmp_path / "cli.json"
    export_answers(repository, participant_name="测试选手", output_path=cli_path)

    assert first_status["total"] == second_status["total"] == 100
    assert web_response.status_code == 200
    download = second_client.get(web_response.json()["download_url"])
    assert download.content == cli_path.read_bytes()


def test_static_polling_interval_is_at_most_two_seconds(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    seed_exportable_workspace(JsonWorkspaceRepository(workspace), 1)
    script = TestClient(create_app(workspace)).get("/static/app.js").text
    assert "2000" in script
    assert "poll" in script
