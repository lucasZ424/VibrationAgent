"""FastAPI HTTP entry for Phase-0 development."""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from apps._bootstrap import ensure_local_imports

APP_ROOT = ensure_local_imports(__file__)

from apps.api.auth import is_authorized  # noqa: E402
from apps.api.middleware.rate_limit import InMemoryRateLimiter  # noqa: E402
from vibration_agent.config import Settings, load  # noqa: E402
from vibration_agent.ingestion.pipeline import chunk_documents, ingest as plan_ingestion  # noqa: E402
from vibration_agent.orchestrator import TutorOrchestrator  # noqa: E402
from vibration_agent.schemas import (  # noqa: E402
    PHASE0_ACTIVE_SKILLS,
    PHASE0_DEFERRED_SKILLS,
    ApiErrorItem,
    ApiErrorResponse,
    ApiHealthResponse,
    ApiIngestionRequest,
    ApiIngestionResponse,
    ApiIngestionResult,
    ApiQueryRequest,
    ApiQueryResponse,
    ApiScopeResponse,
    SkillStatus,
)

app = FastAPI(title="Vibration Agent API")
logger = logging.getLogger(__name__)
rate_limiter = InMemoryRateLimiter()
UI_DIR = APP_ROOT / "apps" / "ui"
if UI_DIR.exists():
    app.mount("/operator/assets", StaticFiles(directory=UI_DIR), name="operator-assets")


class ApiHandledError(Exception):
    def __init__(self, exc: Exception, *, loc: list[str], status_code: int | None = None) -> None:
        super().__init__(str(exc))
        self.exc = exc
        self.loc = loc
        self.status_code = status_code


@lru_cache(maxsize=8)
def get_settings(workspace: str | None = None) -> Settings:
    return load(Path(workspace) if workspace else None)


@lru_cache(maxsize=1)
def get_orchestrator() -> TutorOrchestrator:
    return TutorOrchestrator()


def _configure_cors() -> None:
    try:
        settings = get_settings()
    except Exception:
        return
    if not settings.api.cors_enabled:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


_configure_cors()


def _http_status_for_exception(exc: Exception) -> int:
    if isinstance(exc, FileNotFoundError):
        return 404
    if isinstance(exc, PermissionError):
        return 403
    if isinstance(exc, (ValueError, ValidationError)):
        return 400
    return 500


def _status_from_result(result: dict[str, Any]) -> SkillStatus:
    status = result.get("status")
    if status == "ok":
        return "ok"
    if status == "insufficient":
        return "insufficient"
    if status == "fail":
        return "fail"
    raise ValueError(f"Unexpected pipeline status: {status!r}")


def _api_error_response(exc: Exception, *, loc: list[str], status_code: int | None = None) -> JSONResponse:
    payload = ApiErrorResponse(
        detail=[
            ApiErrorItem(
                loc=loc,
                reason=str(exc) or type(exc).__name__,
                error_type=type(exc).__name__,
            )
        ]
    )
    return JSONResponse(
        status_code=status_code or _http_status_for_exception(exc),
        content=payload.model_dump(mode="json"),
    )


def _raise_api_error(exc: Exception, *, loc: list[str], status_code: int | None = None) -> None:
    raise ApiHandledError(exc, loc=loc, status_code=status_code)


def _enforce_auth(request: Request, settings: Settings) -> None:
    if not is_authorized(request, settings.api):
        _raise_api_error(PermissionError("Missing or invalid API token."), loc=["headers", "x-api-key"], status_code=401)


def _enforce_rate_limit(request: Request, settings: Settings) -> None:
    if not settings.api.rate_limit_enabled:
        return
    client_host = request.client.host if request.client else "unknown"
    key = f"{client_host}:{request.url.path}"
    if not rate_limiter.allow(key, limit=settings.api.rate_limit_per_minute):
        _raise_api_error(PermissionError("API rate limit exceeded."), loc=["headers", "x-rate-limit"], status_code=429)


def _enforce_api_controls(request: Request, settings: Settings) -> None:
    _enforce_auth(request, settings)
    _enforce_rate_limit(request, settings)


def _is_relative_to(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _resolve_workspace_path(raw_path: str, settings: Settings) -> Path:
    workspace = settings.paths.workspace.resolve()
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = workspace / candidate
    resolved = candidate.resolve(strict=False)
    if not _is_relative_to(resolved, workspace):
        raise PermissionError(f"Path is outside the configured workspace: {raw_path}")
    return resolved


@app.exception_handler(ApiHandledError)
async def api_exception_handler(request: Request, exc: ApiHandledError) -> JSONResponse:
    return _api_error_response(exc.exc, loc=exc.loc, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        ApiErrorItem(
            loc=[str(part) for part in error.get("loc", [])],
            reason=str(error.get("msg", "Invalid request")),
            error_type=str(error.get("type", "request_validation_error")),
        )
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=ApiErrorResponse(detail=details).model_dump(mode="json"),
    )


def _query_constraints(request: ApiQueryRequest) -> dict[str, Any]:
    constraints = dict(request.constraints)
    if request.chunks_jsonl:
        constraints["chunk_paths"] = request.chunks_jsonl
    if request.chunks_dir:
        constraints["chunks_dir"] = request.chunks_dir
    if request.top_k is not None:
        constraints["top_k"] = request.top_k
    if request.scope:
        constraints["scope"] = request.scope
    return constraints


def _ingestion_result(result: dict[str, Any]) -> ApiIngestionResult:
    return ApiIngestionResult(
        status=_status_from_result(result),
        stage=result.get("stage"),
        input_path=result.get("input_path"),
        document_count=result.get("document_count"),
        documents=result.get("documents") or [],
        warnings=result.get("warnings") or [],
    )


def _task_id_from_output(output: Any) -> str | None:
    structured = getattr(output, "structured_result", {})
    task_id = structured.get("task_id") if isinstance(structured, dict) else None
    return task_id if isinstance(task_id, str) else None


def _disabled_dependency(name: str) -> dict[str, Any]:
    return {"status": "disabled", "detail": f"{name} is disabled"}


def _postgres_dependency(settings: Settings) -> dict[str, Any]:
    if not settings.database.postgres_enabled:
        return _disabled_dependency("postgres")
    if not settings.database.postgres_url:
        return {"status": "fail", "detail": "POSTGRES_ENABLED=true but POSTGRES_URL is empty"}
    try:
        from vibration_agent.storage.postgres_client import connect

        conn = connect(settings.database.postgres_url, connect_timeout=settings.database.postgres_timeout)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        finally:
            conn.close()
    except Exception as exc:
        return {"status": "fail", "detail": f"{type(exc).__name__}: {exc}"}
    return {"status": "ok", "detail": "postgres reachable"}


def _qdrant_dependency(settings: Settings) -> dict[str, Any]:
    if not settings.database.qdrant_enabled:
        return _disabled_dependency("qdrant")
    try:
        from vibration_agent.storage.qdrant import runtime_client

        client = runtime_client(settings)
        if hasattr(client, "get_collection"):
            client.get_collection(settings.database.qdrant_collection)
    except Exception as exc:
        return {"status": "fail", "detail": f"{type(exc).__name__}: {exc}"}
    return {"status": "ok", "detail": "qdrant reachable"}


def _health_dependencies(settings: Settings) -> dict[str, dict[str, Any]]:
    return {
        "postgres": _postgres_dependency(settings),
        "qdrant": _qdrant_dependency(settings),
    }


def _health_status(dependencies: dict[str, dict[str, Any]]) -> str:
    statuses = [str(item.get("status")) for item in dependencies.values()]
    if not any(status == "fail" for status in statuses):
        return "ok"
    if statuses and all(status == "fail" for status in statuses):
        return "fail"
    return "degraded"


@app.get("/operator", response_class=FileResponse)
def operator_ui() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")


@app.get("/health", response_model=ApiHealthResponse)
def health(request: Request, workspace: str | None = None) -> ApiHealthResponse:
    try:
        settings = get_settings(workspace)
        _enforce_api_controls(request, settings)
    except ApiHandledError:
        raise
    except Exception as exc:
        _raise_api_error(exc, loc=["query", "workspace"])
    dependencies = _health_dependencies(settings)
    status = _health_status(dependencies)
    return ApiHealthResponse(
        status=status,
        app=settings.app_name,
        workspace=str(settings.paths.workspace),
        default_user_mode=settings.default_user_mode,
        phase0_pipeline=settings.phase0_pipeline,
        dependencies=dependencies,
    )


@app.get("/scope", response_model=ApiScopeResponse)
def scope(request: Request, workspace: str | None = None) -> ApiScopeResponse:
    try:
        settings = get_settings(workspace)
        _enforce_api_controls(request, settings)
    except ApiHandledError:
        raise
    except Exception as exc:
        _raise_api_error(exc, loc=["query", "workspace"])
    return ApiScopeResponse(
        active_skills=list(PHASE0_ACTIVE_SKILLS),
        deferred_skills=list(PHASE0_DEFERRED_SKILLS),
        phase0_pipeline=settings.phase0_pipeline,
    )


@app.post(
    "/ingest",
    response_model=ApiIngestionResponse,
    responses={
        400: {"model": ApiErrorResponse},
        403: {"model": ApiErrorResponse},
        404: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
def ingest_documents(http_request: Request, request: ApiIngestionRequest) -> ApiIngestionResponse:
    try:
        settings = get_settings(request.workspace)
        input_path = _resolve_workspace_path(request.path, settings)
        _enforce_api_controls(http_request, settings)
        if request.plan_only:
            raw_result = plan_ingestion(
                input_path,
                recursive=request.recursive,
                settings=settings,
            )
        else:
            raw_result = chunk_documents(
                input_path,
                recursive=request.recursive,
                max_pages=request.max_pages,
                write_output=request.write_output,
                keep_images=request.keep_images,
                source_type=str(request.source_type),
                settings=settings,
            )
        result = _ingestion_result(raw_result)
    except ApiHandledError:
        raise
    except Exception as exc:
        _raise_api_error(exc, loc=["body", "path"])

    return ApiIngestionResponse(
        workspace=str(settings.paths.workspace),
        status=result.status,
        result=result,
    )


@app.post(
    "/query",
    response_model=ApiQueryResponse,
    responses={
        400: {"model": ApiErrorResponse},
        403: {"model": ApiErrorResponse},
        404: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
def query(http_request: Request, request: ApiQueryRequest) -> ApiQueryResponse:
    try:
        settings = get_settings(request.workspace)
        _enforce_api_controls(http_request, settings)
        output = get_orchestrator().handle_query(
            request.query,
            context=request.context,
            constraints=_query_constraints(request),
            user_mode=request.user_mode,
            task_id=request.task_id,
        )
        structured = output.structured_result
        supervisor_status = structured.get("supervisor_status") if isinstance(structured, dict) else None
        supervisor_invocations = structured.get("supervisor_invocations") if isinstance(structured, dict) else None
        logger.info(
            "query supervisor_status=%s supervisor_invocations=%s",
            supervisor_status or "not_triggered",
            supervisor_invocations if supervisor_invocations is not None else 0,
        )
    except ApiHandledError:
        raise
    except Exception as exc:
        _raise_api_error(exc, loc=["body", "query"])

    return ApiQueryResponse(
        workspace=str(settings.paths.workspace),
        status=output.status,
        task_id=_task_id_from_output(output),
        output=output,
    )
