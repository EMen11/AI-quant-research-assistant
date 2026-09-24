"""FastAPI routes with stable sanitized public errors."""

from __future__ import annotations

import os

from fastapi import Depends, FastAPI, Header, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ai_quant.api.schemas import (
    AnalysisCreate,
    AnalysisResponse,
    ApiErrorCode,
    ErrorResponse,
    EvaluationResponse,
    EvidenceResponse,
    HealthResponse,
    ReviewCreate,
    ReviewResponse,
)
from ai_quant.api.service import (
    AnalysisService,
    BusinessConflict,
    CorrectionUnrepresentable,
    ResourceNotFound,
)
from ai_quant.persistence import IdempotencyConflict, PersistenceConflict, create_session_factory


def create_app(service: AnalysisService | None = None) -> FastAPI:
    app = FastAPI(
        title="AI Quant Research Assistant local API",
        version="0.1.0",
        description=(
            "Local persistent research API. Reviewer names are entered, unverified and "
            "unauthenticated. Frozen fixtures are never represented as live market data."
        ),
    )
    selected = service or _service_from_environment()

    def dependency() -> AnalysisService:
        return selected

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, _error):  # type: ignore[no-untyped-def]
        return _error_response(422, "invalid_request", "Request validation failed.")

    @app.exception_handler(ResourceNotFound)
    async def not_found(_request, error: ResourceNotFound):  # type: ignore[no-untyped-def]
        return _error_response(404, "not_found", str(error))

    @app.exception_handler(IdempotencyConflict)
    async def idempotency_conflict(_request, error):  # type: ignore[no-untyped-def]
        return _error_response(409, "conflict", str(error))

    @app.exception_handler(CorrectionUnrepresentable)
    async def correction_unrepresentable(_request, error):  # type: ignore[no-untyped-def]
        return _error_response(409, "correction_unrepresentable", str(error))

    @app.exception_handler(BusinessConflict)
    async def business_conflict(_request, error):  # type: ignore[no-untyped-def]
        return _error_response(409, "conflict", str(error))

    @app.exception_handler(PersistenceConflict)
    async def persistence_conflict(_request, _error):  # type: ignore[no-untyped-def]
        return _error_response(409, "persistence_conflict", "Persistent state conflict.")

    @app.exception_handler(Exception)
    async def internal_error(_request, _error):  # type: ignore[no-untyped-def]
        return _error_response(500, "internal_error", "Internal server error.")

    @app.post(
        "/analyses",
        response_model=AnalysisResponse,
        status_code=201,
        responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    )
    def create_analysis(
        request: AnalysisCreate,
        response: Response,
        idempotency_key: str = Header(
            min_length=8, max_length=200, pattern=r".*\S.*"
        ),
        application: AnalysisService = Depends(dependency),
    ) -> AnalysisResponse:
        result, created = application.create_analysis(request, idempotency_key)
        response.status_code = 201 if created else 200
        return result

    @app.get("/analyses/{analysis_id}", response_model=AnalysisResponse)
    def get_analysis(
        analysis_id: str, application: AnalysisService = Depends(dependency)
    ) -> AnalysisResponse:
        return application.get_analysis(analysis_id)

    @app.get("/analyses/{analysis_id}/evidence", response_model=list[EvidenceResponse])
    def get_evidence(
        analysis_id: str, application: AnalysisService = Depends(dependency)
    ) -> tuple[EvidenceResponse, ...]:
        return application.get_evidence(analysis_id)

    @app.post(
        "/analyses/{analysis_id}/reviews",
        response_model=ReviewResponse,
        status_code=201,
    )
    def create_review(
        analysis_id: str,
        request: ReviewCreate,
        application: AnalysisService = Depends(dependency),
    ) -> ReviewResponse:
        return application.create_review(analysis_id, request)

    @app.get("/evaluations/latest", response_model=EvaluationResponse)
    def latest_evaluation(
        application: AnalysisService = Depends(dependency),
    ) -> EvaluationResponse:
        return application.latest_evaluation()

    @app.get("/health", response_model=HealthResponse)
    def health(application: AnalysisService = Depends(dependency)) -> HealthResponse:
        application.health()
        return HealthResponse(status="ok", database="reachable")

    return app


def _service_from_environment() -> AnalysisService:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for the FastAPI process.")
    return AnalysisService(create_session_factory(database_url))


def _error_response(status: int, code: ApiErrorCode, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message}},
    )
