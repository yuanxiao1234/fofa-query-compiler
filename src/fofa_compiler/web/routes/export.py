from __future__ import annotations

import hashlib
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from fofa_compiler.application.export_answers import export_answers
from fofa_compiler.application.export_gates import preflight_export
from fofa_compiler.web.common import container

router = APIRouter()


@router.get("/export")
def export_page(request: Request):  # type: ignore[no-untyped-def]
    report = preflight_export(container(request).workspace)
    return request.app.state.templates.TemplateResponse(
        request=request, name="export.html", context={"report": report}
    )


@router.post("/api/v1/export")
async def export_api(request: Request):  # type: ignore[no-untyped-def]
    body = await request.json()
    app_container = container(request)
    participant = str(body.get("participant", ""))
    export_id = (
        "export-"
        + hashlib.sha256(
            f"{participant}\0{app_container.clock.now().isoformat()}".encode()
        ).hexdigest()[:20]
    )
    relative_path = f"exports/{export_id}-answer.json"
    target = app_container.workspace.root / relative_path
    summary = export_answers(
        app_container.workspace, participant_name=participant, output_path=target
    )
    metadata = {
        **asdict(summary),
        "export_id": export_id,
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "created_at": app_container.clock.now().isoformat(),
        "download_url": f"/api/v1/exports/{export_id}/download",
    }
    app_container.workspace.save_json(f"exports/{export_id}.metadata.json", metadata)
    return metadata


@router.get("/api/v1/exports/{export_id}/download")
def download(request: Request, export_id: str) -> FileResponse:
    if not export_id.startswith("export-") or not export_id[7:].isalnum():
        raise HTTPException(404, "导出文件不存在")
    target = container(request).workspace.root / "exports" / f"{export_id}-answer.json"
    if not target.is_file():
        raise HTTPException(404, "导出文件不存在")
    return FileResponse(target, media_type="application/json", filename="answer.json")
