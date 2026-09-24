from __future__ import annotations

import secrets
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from fofa_compiler.application.container import build_container
from fofa_compiler.domain.errors import ExportBlockedError, FofaCompilerError, ValidationError
from fofa_compiler.web.routes import export, generation, packages, questions, review

WEB_ROOT = Path(__file__).parent
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1", "testserver"}


def create_app(workspace_root: Path) -> FastAPI:
    app = FastAPI(title="FOFA 查询编译器", docs_url=None, redoc_url=None)
    app.state.container = build_container(workspace_root)
    app.state.csrf_token = secrets.token_urlsafe(32)
    app.state.templates = Jinja2Templates(directory=WEB_ROOT / "templates")
    app.mount("/static", StaticFiles(directory=WEB_ROOT / "static"), name="static")

    @app.middleware("http")
    async def local_security(request: Request, call_next):  # type: ignore[no-untyped-def]
        host_header = request.headers.get("host", "")
        host = urlparse(f"//{host_header}").hostname or ""
        if host not in ALLOWED_HOSTS:
            return JSONResponse({"error": {"code": "INVALID_HOST"}}, status_code=400)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            origin_host = urlparse(origin).hostname if origin else None
            if (
                origin_host not in ALLOWED_HOSTS
                or request.headers.get("x-csrf-token") != app.state.csrf_token
            ):
                return JSONResponse({"error": {"code": "CSRF_REJECTED"}}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
        if "fofa_session" not in request.cookies:
            response.set_cookie(
                "fofa_session", secrets.token_urlsafe(32), httponly=True, samesite="strict"
            )
        return response

    @app.exception_handler(FofaCompilerError)
    async def domain_error(request: Request, exc: FofaCompilerError) -> JSONResponse:
        status = 423 if isinstance(exc, ExportBlockedError) else 422
        if isinstance(exc, ValidationError) and "证据" in exc.message:
            status = 423
        return JSONResponse(
            status_code=status,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "question_id": exc.location.question_id,
                    "details": exc.details,
                    "request_id": request.state.request_id
                    if hasattr(request.state, "request_id")
                    else "local",
                }
            },
        )

    @app.exception_handler(ValueError)
    async def value_error(_request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "INVALID_VALUE", "message": str(exc)}},
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    for router in (
        packages.router,
        generation.router,
        questions.router,
        review.router,
        export.router,
    ):
        app.include_router(router)
    return app
