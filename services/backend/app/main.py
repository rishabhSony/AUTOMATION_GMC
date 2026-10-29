import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import cases, exports, files, pipeline, reference, workbench
from app.core.auth import dev_mock_auth_enabled
from app.core.config import get_settings
from app.services.extractor import use_mock_ai

app = FastAPI(title="QuotePulse GMC API")

if dev_mock_auth_enabled():
    logging.getLogger("uvicorn.error").warning(
        "DEV MOCK AUTH is ON: X-Dev-User-Id headers are trusted. Never enable outside development."
    )

# The Next.js workbench calls the API from the browser with a Clerk Bearer token.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().CORS_ALLOWED_ORIGINS.split(",") if o.strip()],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Dev-User-Id", "X-Dev-User-Role"],
    expose_headers=["Content-Disposition", "X-Archive-Path", "X-Audit-Log-Id"],
)


@app.get("/api/v1/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "dev_mock_auth": dev_mock_auth_enabled(),
        "mock_ai": use_mock_ai(),
        "storage_backend": settings.STORAGE_BACKEND,
    }


app.include_router(cases.router, prefix="/api/v1")
app.include_router(workbench.router, prefix="/api/v1")
app.include_router(exports.router, prefix="/api/v1")
app.include_router(pipeline.router, prefix="/api/v1")
app.include_router(reference.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
