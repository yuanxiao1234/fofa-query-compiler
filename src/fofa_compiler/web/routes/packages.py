from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile

from fofa_compiler.application.import_package import ImportRequest, import_package
from fofa_compiler.web.common import container, package_or_none

router = APIRouter()
MAX_UPLOAD_BYTES = 8 * 1024 * 1024


@router.get("/")
def dashboard(request: Request):  # type: ignore[no-untyped-def]
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"package": package_or_none(request)},
    )


@router.get("/import")
def import_page(request: Request):  # type: ignore[no-untyped-def]
    return request.app.state.templates.TemplateResponse(
        request=request, name="import.html", context={}
    )


@router.post("/api/v1/import")
async def import_api(
    request: Request,
    questions: Annotated[UploadFile, File()],
    package: Annotated[UploadFile, File()],
    template: Annotated[UploadFile, File()],
) -> dict[str, object]:
    documents = []
    for upload in (questions, package, template):
        data = await upload.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError("上传文件超过 8 MB")
        documents.append((Path(upload.filename or "input").name, data))
    with tempfile.TemporaryDirectory(prefix="fofa-import-") as raw_dir:
        directory = Path(raw_dir)
        paths = []
        for index, (name, data) in enumerate(documents):
            path = directory / f"{index}-{name}"
            path.write_bytes(data)
            paths.append(path)
        app_container = container(request)
        imported = import_package(
            ImportRequest(paths[0], paths[1], paths[2]),
            repository=app_container.workspace,
            now=app_container.clock.now(),
        )
    return {"package_id": imported.package_id, "total": len(imported.questions)}
