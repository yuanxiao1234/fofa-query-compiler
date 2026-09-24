from __future__ import annotations

import hashlib
import threading
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from fofa_compiler.application.container import ApplicationContainer
from fofa_compiler.application.generate_answers import generate_answers
from fofa_compiler.domain.models import CompetitionPackage
from fofa_compiler.infrastructure.semantic_parser import SemanticParser
from fofa_compiler.web.common import container

router = APIRouter()


class GenerationManager:
    def __init__(self, app_container: ApplicationContainer) -> None:
        self.container = app_container
        self.lock = threading.Lock()
        self.active_job_id: str | None = None

    def start(self) -> dict[str, object]:
        with self.lock:
            if self.active_job_id is not None:
                raise HTTPException(409, "已有生成任务正在运行")
            package = self.container.workspace.load_model("package.json", CompetitionPackage)
            now = self.container.clock.now()
            job_id = (
                "web-generate-"
                + hashlib.sha256(f"{package.run_id}\0{now.isoformat()}".encode()).hexdigest()[:16]
            )
            value: dict[str, object] = {
                "job_id": job_id,
                "status": "queued",
                "total": len(package.questions),
                "processed": 0,
                "generated": 0,
                "refused": 0,
                "failed": 0,
                "blocked": 0,
            }
            self.container.workspace.save_json(f"jobs/{job_id}.json", value)
            self.active_job_id = job_id
            threading.Thread(
                target=self._run, args=(job_id, package), daemon=True, name=job_id
            ).start()
            return value

    def _run(self, job_id: str, package: CompetitionPackage) -> None:
        value = self.container.workspace.load_json(f"jobs/{job_id}.json")
        value["status"] = "running"
        self.container.workspace.save_json(f"jobs/{job_id}.json", value)
        try:
            for question in package.questions:
                summary = generate_answers(
                    repository=self.container.workspace,
                    audit_log=self.container.audit_log,
                    parser=SemanticParser(),
                    now=self.container.clock.now(),
                    question_id=question.question_id,
                )
                value["processed"] = int(value["processed"]) + 1
                value["generated"] = int(value["generated"]) + summary.generated
                value["refused"] = int(value["refused"]) + summary.refused
                value["failed"] = int(value["failed"]) + summary.failed
                self.container.workspace.save_json(f"jobs/{job_id}.json", value)
            value["status"] = "completed_with_errors" if value["failed"] else "completed"
        except Exception:
            value["status"] = "failed"
        finally:
            self.container.workspace.save_json(f"jobs/{job_id}.json", value)
            with self.lock:
                self.active_job_id = None


def _manager(request: Request) -> GenerationManager:
    manager = getattr(request.app.state, "generation_manager", None)
    if not isinstance(manager, GenerationManager):
        manager = GenerationManager(container(request))
        request.app.state.generation_manager = manager
    return manager


@router.post("/api/v1/generation-jobs")
def generate_api(request: Request) -> dict[str, object]:
    return _manager(request).start()


@router.get("/api/v1/jobs/{job_id}")
@router.get("/jobs/{job_id}")
def job(request: Request, job_id: str):  # type: ignore[no-untyped-def]
    repository = container(request).workspace
    path = repository.root / "jobs" / f"{job_id}.json"
    if not path.is_file():
        raise HTTPException(404, "任务不存在")
    return repository.load_json(f"jobs/{job_id}.json")


@router.get("/api/v1/jobs/{job_id}/events")
def job_events(request: Request, job_id: str) -> StreamingResponse:
    value = job(request, job_id)

    def stream() -> Iterator[str]:
        yield f"event: progress.updated\ndata: {value}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
